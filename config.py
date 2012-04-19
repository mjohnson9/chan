import os
import jinja2
from google.appengine.ext import db

def humanize_bytes(bytes, precision=1): # It's kind of dumb, but I couldn't put this in utils.py because it would cause a circular dependency
	abbrevs = (
		(1<<50L, 'PB'),
		(1<<40L, 'TB'),
		(1<<30L, 'GB'),
		(1<<20L, 'MB'),
		(1<<10L, 'kB'),
		(1, 'bytes')
		)
	if bytes == 1:
		return '1 byte'
	for factor, suffix in abbrevs:
		if bytes >= factor:
			break
	return '%.*f %s' % (precision, bytes / factor, suffix)

VERSION_ID = os.environ["CURRENT_VERSION_ID"].split('.')[1]

MAX_FILE_SIZE_BYTES = 6815744

MAX_FILE_SIZE_STRING = humanize_bytes(float(MAX_FILE_SIZE_BYTES))

COUNTER_SHARDS = 20

GLOBAL_VARS = {'version_id': VERSION_ID, 'max_file_size': MAX_FILE_SIZE_BYTES, 'max_file_size_human': MAX_FILE_SIZE_STRING, 'datastore_reads': db.READ_CAPABILITY, 'datastore_writes': db.WRITE_CAPABILITY}

DEV_SERVER = os.environ['SERVER_SOFTWARE'].startswith('Development')

DEV_MODE = DEV_SERVER
if DEV_MODE:
	import logging

	logging.warn('In development mode')
	jinja_environment = jinja2.Environment(
		loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
		extensions=['pyjade.ext.jinja.PyJadeExtension']
	)
else:
	from google.appengine.api import memcache

	jinja_environment = jinja2.Environment(
		loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
		bytecode_cache=jinja2.MemcachedBytecodeCache(memcache),
		extensions=['pyjade.ext.jinja.PyJadeExtension']
	)

jinja_environment.globals.update(GLOBAL_VARS)