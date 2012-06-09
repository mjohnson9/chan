import logging
import random

from webapp2 import cached_property
from google.appengine.ext import ndb
from google.appengine.api import memcache

import ipaddr
import utils
import config

class CounterShard(ndb.Model):
	count = ndb.IntegerProperty(required = True)

	@classmethod
	def get_key(cls, name, shard_id):
		return ndb.Key(cls, '/%s/%s' % (name, shard_id))

class Counter(object):
	_NOT_SET_VAL = "N"
	_USE_MEMCACHE = False

	def __init__(self, name, start_count=0):
		self._name = name
		self._start = start_count
		self._keys = {}
		self._memcache_key_prefix = 'counter/%s/' % self._name

	def _get_key(self, shard_id):
		if shard_id not in self._keys:
			self._keys[shard_id] = CounterShard.get_key(self._name, shard_id)
		return self._keys[shard_id]

	# Checks for existence. Creates model if there is none. Returns (model, created).
	@ndb.tasklet
	def _check_existence_async(self, shard_id):
		our_key = self._get_key(shard_id)
		our_model = yield our_key.get_async()
		if our_model:
			raise ndb.Return(our_model, False)
		else:
			our_model = CounterShard(key = our_key, count = 0)
			raise ndb.Return(our_model, True)

	@ndb.tasklet
	def get_async(self):
		ctx = ndb.get_context()

		shard_ids = range(0, config.COUNTER_SHARDS)

		shard_str_ids = [str(i) for i in shard_ids]

		shard_values = {}

		if self._USE_MEMCACHE:
			#memcache_checks = yield ctx.memcache_get_multi(keys=shard_str_ids, key_prefix=self._memcache_key_prefix)
			memcache_check_rpcs = []
			for shard_id_str in shard_str_ids:
				memcache_check_rpcs.append(ctx.memcache_get(key=self._memcache_key_prefix+shard_id_str))

			memcache_checks = yield memcache_check_rpcs

			i = 0
			for val in memcache_checks:
				if val is not None:
					shard_values[i] = val
				i += 1

		database_shards = []
		database_shard_ids = []

		for shard_id in shard_ids:
			if shard_id not in shard_values:
				database_shards.append(self._get_key(shard_id))
				database_shard_ids.append(shard_id)

		database_shard_ids.reverse()

		database_shards_rpc = []
		for database_shard in database_shards:
			database_shards_rpc.append(ctx.get(database_shard))

		database_shards = yield database_shards_rpc

		if self._USE_MEMCACHE:
			memcache_set_dict = {}

		for shard in database_shards:
			shard_id = database_shard_ids.pop()
			if shard is None:
				shard_values[shard_id] = self._NOT_SET_VAL
				if self._USE_MEMCACHE:
					memcache_set_dict[str(shard_id)] = self._NOT_SET_VAL
			else:
				shard_values[shard_id] = shard.count
				if self._USE_MEMCACHE:
					memcache_set_dict[str(shard_id)] = shard.count


		if self._USE_MEMCACHE:
			memcache_set_rpcs = []
			for key, value in memcache_set_dict.iteritems():
				memcache_set_rpcs.append(ctx.memcache_set(key=self._memcache_key_prefix + key, value=value))

			yield memcache_set_rpcs

		return_value = self._start

		for value in shard_values.itervalues():
			if value != self._NOT_SET_VAL:
				return_value += value

		raise ndb.Return(return_value)

	@ndb.tasklet
	@ndb.transactional
	def change_async(self, value):
		ctx = ndb.get_context()

		our_shard_id = random.randint(0, config.COUNTER_SHARDS-1)

		our_model, _ = yield self._check_existence_async(our_shard_id)

		our_model.count += value

		yield our_model.put_async()

		if self._USE_MEMCACHE:
			yield ctx.memcache_delete(key=self._memcache_key_prefix + str(our_shard_id))

	def inc_async(self):
		return self.change_async(1)

	def dec_async(self):
		return self.change_async(-1)

class Ban(ndb.Model):
	reason = ndb.TextProperty(indexed=False, required=False)

	@classmethod
	def get_key(cls, ip):
		return ndb.Key(cls, ip)

POST_ID_COUNTER = Counter('PostID')

class Post(ndb.Model):
	INDEX_PAGE_KEY = 'index/threads'
	POST_KEY_PREFIX = 'post/query/'

	parent_thread = ndb.KeyProperty(required=False, default=None, indexed=True)
	thread_bumped = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

	posted = ndb.DateTimeProperty(auto_now_add=True, indexed=True)

	username = ndb.StringProperty(required=False, indexed=False)
	capcode = ndb.StringProperty(required=False, indexed=False)
	email = ndb.StringProperty(required=False, indexed=False)
	user = ndb.UserProperty(required=False, indexed=False)

	image = ndb.BlobKeyProperty(required=False, indexed=False)
	image_width = ndb.IntegerProperty(required=False, indexed=False)
	image_height = ndb.IntegerProperty(required=False, indexed=False)
	image_url = ndb.TextProperty(required=False, indexed=False)

	subject = ndb.StringProperty(required=False, indexed=False)
	comment = ndb.TextProperty(required=False, indexed=False)

	ip = ndb.IntegerProperty(required=True, indexed=False)

	@cached_property
	def ip_string(self):
		return str(ipaddr.IPAddress(self.ip))

	@property
	def posted_string(self):
		return self.posted.strftime("%y/%m/%d(%a)%H:%M:%S")

	@classmethod
	def get_key(cls, id):
		return ndb.Key(cls, id)

	@staticmethod
	@ndb.tasklet
	def get_next_id_async():
		yield POST_ID_COUNTER.inc_async()
		value = yield POST_ID_COUNTER.get_async()
		raise ndb.Return(value)

	@classmethod
	def get_index_page_query(cls):
		return cls.query(cls.parent_thread == None).order(-cls.thread_bumped)

	def _post_put_hook(self, future):
		memcache.delete(self.INDEX_PAGE_KEY, seconds=2)
		if self.parent_thread is not None:
			parent_id = self.parent_thread.id()
			if memcache.delete(self.POST_KEY_PREFIX + str(parent_id), seconds=2):
				logging.debug("Removed %s's memcache entry", parent_id)
			else:
				logging.debug("Failed to remove %s's memcache entry", parent_id)

	@classmethod
	def get_child_posts_query(cls, parent_key):
		return Post.query(cls.parent_thread == parent_key).order(cls.posted)

	@classmethod
	@ndb.tasklet
	def get_index_page_async(cls):
		ctx = ndb.get_context()

		memcache_result = yield ctx.memcache_get(cls.INDEX_PAGE_KEY)
		if memcache_result is not None:
			logging.debug("Got index page from memcache: %s", memcache_result)
			results = yield ndb.get_multi_async([cls.get_key(i) for i in memcache_result])
			raise ndb.Return(results)
		else:
			results = yield cls.get_index_page_query().fetch_async(10)
			if results is not None:
				add_result = yield ctx.memcache_add(cls.INDEX_PAGE_KEY, [i.key.id() for i in results])
				if add_result:
					logging.debug("Added index page to memcache")
				else:
					logging.debug("Did not add index page to memcache")
				raise ndb.Return(results)
		raise ValueError("Failed to get results from query")

	@classmethod
	@ndb.tasklet
	def get_child_posts_async(cls, parent_key):
		id_str = str(parent_key.id())

		ctx = ndb.get_context()

		memcache_result = yield ctx.memcache_get(cls.POST_KEY_PREFIX + id_str)
		if memcache_result is not None:
			logging.debug("Got child posts from memcache: %s", memcache_result)
			raise ndb.Return(ndb.get_multi([cls.get_key(i) for i in memcache_result]))
		else:
			results = yield cls.get_child_posts_query(parent_key).fetch_async()
			if results is not None:
				add_result = yield ctx.memcache_add(cls.POST_KEY_PREFIX + id_str, [i.key.id() for i in results])
				if add_result:
					logging.debug("Added child posts to memcache")
				else:
					logging.debug("Failed to add child posts to memcache")
				raise ndb.Return(results)
		raise ValueError("Failed to get results from query")