import logging
from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.ext.ndb import blobstore

from google.appengine.runtime import DeadlineExceededError

class Operation(object):
	pass

class DeleteOperation(Operation):
	def __init__(self, *args):
		self._delete_objects = []
		for obj in args:
			if isinstance(obj, ndb.Model):
				self._delete_objects.append(obj.key)
			else:
				self._delete_objects.append(obj)

	def perform_action(self, mapper):
		mapper.to_delete.extend(self._delete_objects)

	def __str__(self):
		return "<DeleteOperation: %s>" % self._delete_objects

class BlobstoreDeleteOperation(Operation):
	def __init__(self, *args):
		self._delete_objects = args

	def perform_action(self, mapper):
		mapper.blobstore_to_delete.extend(self._delete_objects)

	def __str__(self):
		return "<BlobstoreDeleteOperation: %s>" % self._delete_objects

class Mapper(object):
	def __init__(self):
		self.to_put = []
		self.to_delete = []
		self.blobstore_to_delete = []

	def map(self, entity):
		"""Updates a single entity.

		Implementers should yield operations.
		"""
		pass

	def finish(self):
		"""Called when the mapper has finished, to allow for any final work to be done."""
		pass

	def get_query(self):
		"""Returns a query over the specified kind, with any appropriate filters applied."""
		# This is a stub method.
		#q = self.KIND.all()
		#for prop, value in self.FILTERS:
		#	q.filter("%s =" % prop, value)
		#q.order("__key__")
		raise NotImplementedError()

	def run(self, batch_size=100):
		"""Starts the mapper running."""
		self._continue(None, batch_size)

	def _batch_write(self):
		"""Writes updates and deletes entities in a batch."""
		logging.debug("Batch writing")
		if self.to_put and len(self.to_put) > 0:
			put_rpcs = ndb.put_multi_async(self.to_put)
		else:
			put_rpcs = None

		if self.to_delete and len(self.to_delete) > 0:
			delete_rpcs = ndb.delete_multi_async(self.to_delete)
		else:
			delete_rpcs = None

		if self.blobstore_to_delete and len(self.blobstore_to_delete) > 0:
			blobstore_delete_rpc = blobstore.delete_async(self.blobstore_to_delete)
		else:
			blobstore_delete_rpc = None

		if put_rpcs:
			for put_rpc in put_rpcs:
				put_rpc.wait()
			self.to_put = []

		if delete_rpcs:
			for delete_rpc in delete_rpcs:
				delete_rpc.wait()
			self.to_delete = []

		if blobstore_delete_rpc:
			blobstore_delete_rpc.wait()
			self.blobstore_to_delete = []

	def _continue(self, start_cursor, batch_size):
		q = self.get_query()
		# If we're resuming, pick up where we left off last time.
		iter = q.iter(start_cursor=start_cursor)
		# Keep updating records until we run out of time.
		try:
			# Steps over the results, returning each entity and its index.
			i = 0
			for entity in iter:
				for operation in self.map(entity):
					operation.perform_action(self)

				# Do updates and deletes in batches.
				#if (i + 1) % batch_size == 0:
				#	self._batch_write()

				i += 1
				# Record the last entity we processed.
			self._batch_write()
		except DeadlineExceededError:
			logging.info("Exceeded deadline")
			# Write any unfinished updates to the datastore.
			self._batch_write()
			# Queue a new task to pick up where we left off.
			deferred.defer(self._continue, iter.cursor_after(), batch_size)
			return
		self.finish()