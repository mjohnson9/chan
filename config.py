import os
from datetime import timedelta

import jinja2
from google.appengine.ext import db, ndb

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

UPLOAD_KEY_EXPIRATION = timedelta(minutes=15)

VERSION_ID = os.environ["CURRENT_VERSION_ID"].split('.')[1]

TRUSTED_FORWARDERS_STR = """204.93.240.0/24
204.93.177.0/24
199.27.128.0/21
173.245.48.0/20
103.22.200.0/22
141.101.64.0/18
108.162.192.0/18
190.93.240.0/20
2400:cb00::/32
2606:4700::/32
2803:f800::/32"""

MAX_FILE_SIZE_BYTES = 6815744

MAX_FILE_SIZE_STRING = humanize_bytes(float(MAX_FILE_SIZE_BYTES))

COUNTER_SHARDS = 20

DB_READ_CAPABILITY = db.READ_CAPABILITY
DB_WRITE_CAPABILITY = db.WRITE_CAPABILITY

GLOBAL_VARS = {'version_id': VERSION_ID, 'max_file_size': MAX_FILE_SIZE_BYTES, 'max_file_size_human': MAX_FILE_SIZE_STRING, 'datastore_reads': DB_READ_CAPABILITY, 'datastore_writes': DB_WRITE_CAPABILITY}

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