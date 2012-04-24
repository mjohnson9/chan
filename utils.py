import re

from google.appengine.api import images

import config
import ipaddr

IMAGE_URL_STRIP_MATCHER = re.compile("^http[s]?://[^/]+", re.IGNORECASE)
IMAGE_URL_PROTOCOL_MATCHER = re.compile("^http://", re.IGNORECASE)

TRUSTED_FORWARDS = []

if config.DEV_SERVER:
	def clean_dev_url(url):
		return IMAGE_URL_STRIP_MATCHER.sub("", url)
else:
	def clean_dev_url(url):
		return url

def get_image_url(image):
	image_url = images.get_serving_url(blob_key=image)

	if image_url:
		if config.DEV_SERVER:
			image_url = IMAGE_URL_STRIP_MATCHER.sub("", image_url)
		else:
			image_url = IMAGE_URL_PROTOCOL_MATCHER.sub("https://", image_url)

	return image_url

lines = config.TRUSTED_FORWARDERS_STR.split("\n")
for line in lines:
	TRUSTED_FORWARDS.append(ipaddr.IPNetwork(line))

def is_trusted_forwarder(ip):
	for forwarder in TRUSTED_FORWARDS:
		if ip in forwarder:
			return True
	return False