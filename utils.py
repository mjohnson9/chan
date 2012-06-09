import logging
import re
import cgi

from google.appengine.api import images

import config
import ipaddr

IMAGE_URL_STRIP_MATCHER = re.compile("^http[s]?://[^/]+", re.IGNORECASE)
IMAGE_URL_PROTOCOL_MATCHER = re.compile("^http://", re.IGNORECASE)

if config.DEV_SERVER:
	def clean_dev_url(url):
		return IMAGE_URL_STRIP_MATCHER.sub("", url)
else:
	def clean_dev_url(url):
		return url

POST_REFERENCE_REGEX = re.compile("&gt;&gt;(\d+)", re.IGNORECASE)

def format_comment(str):
	logging.debug("format_comment: %r", str)
	str = str.strip()
	logging.debug("stripped comment: %r", str)
	str = cgi.escape(str)
	logging.debug("escaped comment: %r", str)
	str = str.replace("\n", "<br/>")
	logging.debug("newlines replaced: %r", str)
	str = POST_REFERENCE_REGEX.sub("<a href=\"/post/\\1#\\1\">&gt;&gt;\\1</a>", str)
	logging.debug("links to other posts replaced: %r", str)
	return str

def get_image_url(image):
	image_url = images.get_serving_url(blob_key=image)

	if image_url:
		if config.DEV_SERVER:
			image_url = IMAGE_URL_STRIP_MATCHER.sub("", image_url)
		else:
			image_url = IMAGE_URL_PROTOCOL_MATCHER.sub("https://", image_url)

	return image_url

TRUSTED_FORWARDS = []

lines = config.TRUSTED_FORWARDERS_STR.split("\n")
for line in lines:
	try:
		thisip = ipaddr.IPNetwork(line)
	except ValueError:
		pass
	else:
		TRUSTED_FORWARDS.append(thisip)

def is_trusted_forwarder(ip):
	for forwarder in TRUSTED_FORWARDS:
		if ip in forwarder:
			return True
	return False