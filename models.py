import utils
import random
import config
from google.appengine.ext import ndb
from google.appengine.api import memcache

class _Counter(ndb.Model):
	count = ndb.IntegerProperty(required = True)

	@classmethod
	def get_key(cls, name, shard_id):
		return ndb.Key(cls, '/%s/%s' % (name, shard_id))

class Counter(object):
	_NOT_SET_VAL = "N"
	_PENDING_CHANGE_VAL = "K"

	def __init__(self, name, start_count=0):
		self._name = name
		self._start = start_count
		self._keys = {}
		self._memcache_key_prefix = 'counter/%s/' % self._name

	def _get_key(self, shard_id):
		if shard_id not in self._keys:
			self._keys[shard_id] = _Counter.get_key(self._name, shard_id)
		return self._keys[shard_id]

	# Checks for existence. Creates model if there is none. Returns (model, created).
	def _check_existence(self, shard_id):
		our_key = self._get_key(shard_id)
		our_model = our_key.get()
		if our_model:
			return our_model, False
		else:
			our_model = _Counter(key = our_key, count = 0)
			return our_model, True

	def get(self):
		shard_ids = range(0, config.COUNTER_SHARDS)

		shard_str_ids = [str(i) for i in shard_ids]

		shard_values = {}

		memcache_checks = memcache.get_multi(keys=shard_str_ids, key_prefix=self._memcache_key_prefix)

		for shard_id, val in memcache_checks.iteritems():
			if val is not None and val != self._PENDING_CHANGE_VAL:
				shard_values[int(shard_id)] = val

		database_shards = []
		database_shard_ids = []

		for shard_id in shard_ids:
			if shard_id not in shard_values:
				database_shards.append(self._get_key(shard_id))
				database_shard_ids.append(shard_id)

		database_shard_ids.reverse()

		database_shards_rpc = ndb.get_multi_async(database_shards)

		memcache_set_dict = {}

		for shard_rpc in database_shards_rpc:
			shard_id = database_shard_ids.pop()
			shard = shard_rpc.get_result()
			if shard is None:
				shard_values[shard_id] = self._NOT_SET_VAL
				memcache_set_dict[str(shard_id)] = self._NOT_SET_VAL
			else:
				shard_values[shard_id] = shard.count
				memcache_set_dict[str(shard_id)] = shard.count

		memcache.set_multi(mapping=memcache_set_dict, key_prefix=self._memcache_key_prefix)

		return_value = self._start

		for value in shard_values.itervalues():
			if value != self._NOT_SET_VAL:
				return_value += value

		return return_value

	@ndb.transactional
	def change(self, value):
		our_shard_id = random.randint(0, config.COUNTER_SHARDS-1)
		our_model, _ = self._check_existence(our_shard_id)
		our_model.count += value
		our_model.put()
		memcache.delete(key='%s%s' % (self._memcache_key_prefix, our_shard_id), seconds=3)

	def inc(self):
		return self.change(1)

	def dec(self):
		return self.change(-1)

POST_ID_COUNTER = Counter('PostID')

class Post(ndb.Model):
	parent_thread = ndb.KeyProperty(required=False, indexed=False)

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

	@property
	def ip_string(self):
		return utils.num_to_dotted_quad(self.ip)

	@classmethod
	def get_key(cls, id):
		return ndb.Key(cls, id)

	@staticmethod
	def get_next_id():
		POST_ID_COUNTER.inc()
		return POST_ID_COUNTER.get()

class Thread(ndb.Model):
	bumped = ndb.DateTimeProperty(auto_now_add=True, indexed=True)
	main_post = ndb.KeyProperty(required=True, kind=Post, indexed=False)

	@classmethod
	def get_key(cls, id):
		return ndb.Key(cls, id)

	@classmethod
	def get_index_page_async(cls, page, size=10):
		return ndb.get_multi_async(cls.query().order(-cls.bumped).fetch(limit=size, offset=page*size, keys_only=True))

	@classmethod
	def get_next_id(cls):
		return cls.allocate_ids(size=1)[0]