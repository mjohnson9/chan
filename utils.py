import config
import re
from google.appengine.api import images

IMAGE_URL_STRIP_MATCHER = re.compile("^http[s]?://[^/]+", re.IGNORECASE)
IMAGE_URL_PROTOCOL_MATCHER = re.compile("^http://", re.IGNORECASE)

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

def dotted_quad_to_num(ip):
	"convert decimal dotted quad string to long integer"

	hexn = ''.join(["%02X" % long(i) for i in ip.split('.')])
	return long(hexn, 16)

def num_to_dotted_quad(n):
	"convert long int to dotted quad string"

	d = 256 * 256 * 256
	q = []
	while d > 0:
		m,n = divmod(n,d)
		q.append(str(m))
		d /= 256

	return '.'.join(q)