import base64
import urllib
try:
	import json
except ImportError:
	from django.utils import simplejson as json

from google.appengine.ext import ndb

import config

__all__ = ['track']

@ndb.tasklet
def track_async(event, properties=None):
	"""
		A simple function for asynchronously logging to the mixpanel.com API on App Engine 
		(Python) using RPC URL Fetch object.
		@param event: The overall event/category you would like to log this data under
		@param properties: A dictionary of key-value pairs that describe the event
		See http://mixpanel.com/api/ for further detail. 
		@return Instance of RPC Object
	"""
	ctx = ndb.get_context()

	if properties is None:
		properties = {}

	if "token" not in properties:
		properties["token"] = config.MIXPANEL_API_KEY
	
	params = {"event": event, "properties": properties}
		
	data = base64.b64encode(json.dumps(params))
	request = "https://api.mixpanel.com/track/?data=" + data
	
	result = yield ctx.urlfetch(request)