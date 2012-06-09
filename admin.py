import logging

from google.appengine.ext import ndb
from google.appengine.ext.ndb import blobstore
from google.appengine.api import memcache

import mapper
import models

MEMCACHE_BAN_PREFIX = 'ban/'

@ndb.tasklet
def check_ip_ban_async(ip):
	"""Checks for an IP ban.

	Args:
		ip: The IPAddress representation of the IP to check.

	Returns:
		A tuple of (banned, reason) where banned is a boolean and reason is a string or None.
	"""
	ctx = ndb.get_context()

	ip_num = int(ip)

	ip_num_str = str(ip_num)

	reason_key = '%s/reason' % ip_num_str

	memcache_rpcs = [ctx.memcache_get(MEMCACHE_BAN_PREFIX + ip_num_str), ctx.memcache_get(MEMCACHE_BAN_PREFIX + reason_key)]

	memcache_result = yield memcache_rpcs

	if memcache_result[0] is not None:
		raise ndb.Return(memcache_result[0], memcache_result[1])
	else:
		our_key = models.Ban.get_key(ip_num)

		our_model = yield ctx.get(our_key)

		if our_model:
			yield ctx.memcache_set(MEMCACHE_BAN_PREFIX + ip_num_str, True), ctx.memcache_set(MEMCACHE_BAN_PREFIX + reason_key, our_model.reason)

			raise ndb.Return(True, our_model.reason)
		else:
			yield ctx.memcache_set(MEMCACHE_BAN_PREFIX + ip_num_str, False)

			raise ndb.Return(False, None)

def get_ip_ban(ip, reason=None):
	our_key = models.Ban.get_key(int(ip))

	our_model = models.Ban(key=our_key, reason=reason)

	return our_model


class DeletePostMapper(mapper.Mapper):
	def __init__(self, thread_id):
		super(DeletePostMapper, self).__init__()
		self._thread_id = thread_id

	def map(self, entity):
		if entity.parent_thread.id() == self._thread_id:
			yield mapper.DeleteOperation(entity)
			if entity.image:
				yield mapper.BlobstoreDeleteOperation(entity.image)

	def get_query(self):
		return models.Post.query(models.Post.parent_thread == models.Post.get_key(self._thread_id))

def delete_post(post_num):
	"""Deletes a post or thread.

	This deletes a post or a thread. If the supplied post number is a thread, it deferrs deletion of child posts for later.

	Args:
		post_num: The number of the post or thread to delete.

	Raises:
		ValueError: Given post ID does not exist.
	"""
	our_key = models.Post.get_key(post_num)

	our_model = our_key.get()

	if our_model:
		if our_model.parent_thread is None:
			mapper = DeletePostMapper(our_key.id())
			mapper.run()

			logging.info("Thread deletion started")
		our_key.delete()
		if our_model.image:
			blobstore.delete([our_model.image])
		if our_model.parent_thread is None:
			memcache.delete(models.Post.POST_KEY_PREFIX + str(our_key.id()))
		else:
			memcache.delete(models.Post.POST_KEY_PREFIX + str(our_model.parent_thread.id()))
	else:
		raise ValueError("Given post ID does not exist.")