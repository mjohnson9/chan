import cgi
from datetime import datetime, timedelta
import logging
import re
import time
import uuid

import webapp2
from google.appengine.ext.ndb import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.api import images

import admin
import config
import ipaddr
import mixpanel
import models
import utils


class HandlerUtils(object):
	THIS_PAGE = ""

	def __init__(self, *args, **kwargs):
		super(HandlerUtils, self).__init__(*args, **kwargs)
		self._is_banned = None
		self._ban_reason = None

		self.check_uuid()

	def check_uuid(self):
		self.current_uuid = self.request.cookies.get('mixpanel-uuid', None)
		if self.current_uuid is None:
			self.current_uuid = str(uuid.uuid4())
			self.response.set_cookie('mixpanel-uuid', self.current_uuid)

	@ndb.tasklet
	def user_is_banned_async(self, ip=None):
		if ip is None: ip = self.user_ip
		if self._is_banned is None:
			self._is_banned, self._ban_reason = yield admin.check_ip_ban_async(ip)
		raise ndb.Return(self._is_banned, self._ban_reason)

	@webapp2.cached_property
	def user_ip(self):
		if 'X-Forwarded-For' in self.request.headers:
			forwarded_for = self.request.remote_addr + ',' + self.request.headers['X-Forwarded-For']
			forwarders = forwarded_for.split(',')
			user_ip = None
			for forwarder_str in forwarders:
				forwarder_str = forwarder_str.strip()
				forwarder = ipaddr.IPAddress(forwarder_str)
				user_ip = forwarder
				if not utils.is_trusted_forwarder(forwarder):
					break
			return user_ip
		else:
			return ipaddr.IPAddress(self.request.remote_addr)

	def render_response(self, _template, **context):
		# Renders a template and writes the result to the response.
		if 'user_is_banned' not in context or 'user_ban_reason' not in context:
			ban_rpc = self.user_is_banned_async()
		else:
			ban_rpc = None

		if 'user' not in context:
			current_user = users.get_current_user()
			if current_user:
				context['user'] = current_user

		if 'user_is_admin' not in context:
			context['user_is_admin'] = users.is_current_user_admin()

		if 'db_writes_enabled' not in context:
			context['db_writes_enabled'] = config.DB_WRITE_CAPABILITY.is_enabled()

		if 'current_page' not in context:
			context['current_page'] = self.THIS_PAGE

		if 'X-PJAX' in self.request.headers and self.request.headers['X-PJAX'].lower() == "true":
			context['pjax'] = True

		if ban_rpc is not None:
			if 'user_is_banned' not in context:
				context['user_is_banned'] = ban_rpc.get_result()[0]

			if 'user_ban_reason' not in context:
				context['user_ban_reason'] = ban_rpc.get_result()[1]

		template = config.jinja_environment.get_template(_template)
		self.response.write(template.render(context))

	@ndb.tasklet
	def mixpanel_track_async(self, event, properties=None):
		if properties is None:
			properties = {}

		if "ip" not in properties:
			properties["ip"] = str(self.user_ip)

		if "time" not in properties:
			properties["time"] = time.time()

		if "mp_name_tag" not in properties:
			current_user = users.get_current_user()
			if current_user:
				properties['mp_name_tag'] = current_user.nickname()

		if "distinct_id" not in properties:
			properties["distinct_id"] = self.current_uuid

		result = yield mixpanel.track_async(event, properties)

		raise ndb.Return(result)

class BaseHandler(HandlerUtils, webapp2.RequestHandler):
	pass

class BaseUploadHandler(HandlerUtils, blobstore_handlers.BlobstoreUploadHandler):
	def _delete_files_async(self, exclude=None):
		if not exclude:
			logging.debug("Deleting all uploaded files...")
			return blobstore.delete_multi_async(self.get_uploads())
		else:
			files = []

			for file in self.get_uploads():
				#if file not in exclude:
				if file != exclude:
					files.append(file)

			logging.debug("Deleting uploaded files: %s", files)
			return blobstore.delete_multi_async(files)

	def _validate_form(self):
		return []

	abort = webapp2.RequestHandler.abort

class ImagePage(blobstore_handlers.BlobstoreDownloadHandler):
	IMAGE_EXPIRATION_TIME = timedelta(days=30)
	IMAGE_EXPIRATION_SECONDS = int(IMAGE_EXPIRATION_TIME.total_seconds())

	@ndb.toplevel
	def get(self, post_id_str):
		post_id = int(post_id_str)

		post_key = models.Post.get_key(post_id)

		post = post_key.get()
		if post and post.image:
			self.response.cache_control.no_cache = None
			self.response.cache_control.public = True
			self.response.cache_control.max_age = self.IMAGE_EXPIRATION_SECONDS

			self.response.expires = datetime.now() + self.IMAGE_EXPIRATION_TIME

			self.send_blob(post.image)
		else:
			self.abort(404)

class IndexPage(BaseHandler):
	THIS_PAGE = "home"

	@ndb.toplevel
	def get(self):
		index_threads_rpc = models.Post.get_index_page_async()
		user_ban_rpc = self.user_is_banned_async()

		db_writes_enabled = config.DB_WRITE_CAPABILITY.is_enabled()

		user_ban = user_ban_rpc.get_result()
		if db_writes_enabled and not user_ban[0]:
			upload_url_rpc = blobstore.create_upload_url_async("/new-thread/%s" % int(self.user_ip), max_bytes_per_blob=config.MAX_FILE_SIZE_BYTES, max_bytes_total=config.MAX_FILE_SIZE_BYTES)

			self.render_response('index.html', upload_url=utils.clean_dev_url(upload_url_rpc.get_result()), threads=index_threads_rpc.get_result(), db_writes_enabled=db_writes_enabled)
		else:
			self.render_response('index.html', threads=index_threads_rpc.get_result(), db_writes_enabled=db_writes_enabled)

class IPPage(BaseHandler):
	@ndb.toplevel
	def get(self, ip_recv):
		is_admin = users.is_current_user_admin()

		if is_admin:
			try:
				ip_to_send = int(ip_recv)
			except ValueError:
				ip_to_send = str(ip_recv)

			try:
				ip = ipaddr.IPAddress(ip_to_send)
			except (ipaddr.AddressValueError, ValueError):
				self.render_response("ipaddr-invalid.html", ip=ip_recv)
			else:
				user_ban_rpc = self.user_is_banned_async(ip)

				self.render_response("ipaddr.html", banned=user_ban_rpc.get_result(), ip=ip)
		else:
			current_user = users.get_current_user()

			if current_user:
				self.abort(403)
			else:
				self.redirect('/login')


class PostPage(BaseHandler):
	@ndb.toplevel
	def get(self, post_id_str):
		post_id = int(post_id_str)

		post_key = models.Post.get_key(post_id)

		post = post_key.get()
		if post:
			if post.parent_thread is None:
				user_ban_rpc = self.user_is_banned_async()
				comment_text = self.request.GET.get('comment', '')

				db_writes_enabled = config.DB_WRITE_CAPABILITY.is_enabled()

				child_posts_rpc = models.Post.get_child_posts_async(post_key)
				user_ban = user_ban_rpc.get_result()
				if db_writes_enabled and not user_ban[0]:
					upload_url_rpc = blobstore.create_upload_url_async("/post/%d/reply/%s" % (post_id, int(self.user_ip)), max_bytes_per_blob=config.MAX_FILE_SIZE_BYTES, max_bytes_total=config.MAX_FILE_SIZE_BYTES)

					self.render_response('post_view.html', main_post=post, upload_url=utils.clean_dev_url(upload_url_rpc.get_result()), child_posts=child_posts_rpc.get_result(), comment=comment_text, db_writes_enabled=db_writes_enabled)
				else:
					self.render_response('post_view.html', main_post=post, child_posts=child_posts_rpc.get_result(), comment=comment_text, db_writes_enabled=db_writes_enabled)
			else:
				if 'comment' in self.request.GET:
					self.redirect('/post/%d?comment=%s#%d' % (post.parent_thread.id(), self.request.GET['comment'], post_id))
				else:
					self.redirect('/post/%d#%d' % (post.parent_thread.id(), post_id))
		else:
			self.abort(404)

class BanPage(BaseHandler):
	THIS_PAGE = "ban"

	def display_page(self, ip=None, reason=None, errors=None, delete=False, success=False):
		if errors is None: errors=[]
		self.render_response('ban.html', ban_ip=ip, errors=errors, delete=delete, reason=reason, action_url=self.request.path_qs, success=not (not success))

	@ndb.toplevel
	def get(self, post_id_str=None, delete=None):
		is_admin = users.is_current_user_admin()

		if is_admin:
			delete = (delete is not None)

			if post_id_str is not None:
				try:
					post_id = int(post_id_str)
				except ValueError:
					self.display_page(errors=['Invalid post ID.'], delete=delete)
				else:
					post_key = models.Post.get_key(post_id)

					post = post_key.get()
					if post:
						self.display_page(ip=post.ip_string, delete=delete)
					else:
						self.display_page(errors=['Post does not exist.'], delete=delete)
			else:
				ban_ip = self.request.GET.get('ip', '')
				self.display_page(delete=delete, ip=ban_ip)
		else:
			current_user = users.get_current_user()

			if current_user:
				self.abort(403)
			else:
				self.redirect('/login')

	@ndb.toplevel
	def post(self, post_id_str=None, delete=""):
		is_admin = users.is_current_user_admin()

		if is_admin:
			delete = (delete is not None and delete != "")

			errors = []

			ban_ip = None
			ban_ip_str_post = self.request.POST.get("banee-ip", "").strip()
			if len(ban_ip_str_post) <= 0:
				errors.append("You must supply an IP.")
			else:
				try:
					ban_ip = ipaddr.IPAddress(ban_ip_str_post)
				except ValueError:
					errors.append("The supplied IP is invalid.")

			ban_reason = self.request.POST.get("ban-reason", "").strip()
			if len(ban_reason) <= 0:
				errors.append("You must supply a reason.")

			if len(errors) > 0:
				self.display_page(errors=errors, ip=ban_ip_str_post, reason=ban_reason, delete=delete)
			else:
				ban_ip_num = int(ban_ip)
				ban_ip_num_str = str(ban_ip_num)

				banned_rpc = admin.check_ip_ban_async(ban_ip)

				ban_key = models.Ban.get_key(ban_ip_num_str)

				if delete:
					post_id = int(post_id_str)

					current_user = users.get_current_user()

					admin.delete_post(post_id)

					logging.info("%s deleted post #%s", current_user.email(), post_id)

				if banned_rpc.get_result()[0]:
					ban = ban_key.get()
					if ban.reason != ban_reason:
						current_user = users.get_current_user()

						logging.info("%s changed %s's ban reason from \"%s\" to \"%s\"", current_user.email(), ban_ip, ban.reason, ban_reason)

						ban.reason = cgi.escape(ban_reason)

						ban.put()

						ban_ip_num_str = str(ban_ip_num)

						memcache.delete_multi([ban_ip_num_str, '%s/reason' % ban_ip_num_str], key_prefix=admin.MEMCACHE_BAN_PREFIX)

						self.display_page(ip=ban_ip_num, reason=ban_reason, success=True, delete=delete)
					else:
						self.display_page(errors=['A ban with that IP and reason already exists.'], ip=str(ban_ip), reason=ban_reason, delete=delete)
				else:
					ban_ip_num_str = str(ban_ip_num)

					ban = models.Ban(key=ban_key, reason=cgi.escape(ban_reason))
					ban.put()

					current_user = users.get_current_user()

					logging.info("%s banned %s with the reason \"%s\"", current_user.email(), ban_ip, ban_reason)

					memcache.delete_multi([ban_ip_num_str, '%s/reason' % ban_ip_num_str], key_prefix=admin.MEMCACHE_BAN_PREFIX)

					self.display_page(ip=str(ban_ip), reason=ban_reason, success=True, delete=delete)
		else:
			current_user = users.get_current_user()

			if current_user:
				self.abort(403)
			else:
				self.redirect('/login')

class LogoutPage(BaseHandler):
	@ndb.toplevel
	def get(self):
		self.redirect(users.create_logout_url('/'))

class LoginPage(BaseHandler):
	@ndb.toplevel
	def get(self):
		self.redirect(users.create_login_url('/'))

class NewThreadPage(BaseUploadHandler):
	@ndb.toplevel
	def post(self, ip_num_str):
		errors = self._validate_form()

		if len(errors) > 0:
			index_threads_rpc = models.Post.get_index_page_async()
			delete_rpc = self._delete_files_async()

			self.render_response("index.html", post_errors=errors, threads=index_threads_rpc.get_result())

			delete_rpc.wait()
		else:
			ip_num = int(ip_num_str)
			ip = ipaddr.IPAddress(ip_num)

			ban_rpc = self.user_is_banned_async(ip)

			if not ban_rpc.get_result()[0]:
				image_info = self.get_uploads()[0]
				image_key = image_info.key()

				delete_rpc = self._delete_files_async(image_info)

				if image_info.size > config.MAX_FILE_SIZE_BYTES:
					index_threads_rpc = models.Post.get_index_page_async()
					blobstore.delete(image_key)
					delete_rpc.wait()
					self.render_response("index.html", post_errors=['The supplied file was too large.'], threads=index_threads_rpc.get_result())
					logging.info("File was too large")
					return

				data = blobstore.fetch_data(image_key, 0, 50000)
				try:
					image_data = images.Image(image_data=data)
					_ = image_data.width
					_ = image_data.height
				except images.NotImageError:
					index_threads_rpc = models.Post.get_index_page_async()
					blobstore.delete(image_key)
					delete_rpc.wait()
					self.render_response("index.html", post_errors=['The supplied file was not an image.'], threads=index_threads_rpc.get_result())
					logging.info("Not an image", exc_info=True)
					return
				except images.Error:
					index_threads_rpc = models.Post.get_index_page_async()
					blobstore.delete(image_key)
					delete_rpc.wait()
					self.render_response("index.html", post_errors=['An unknown error occurred when we attempted to process the file you supplied.'], threads=index_threads_rpc.get_result())
					logging.warn("Unknown error when processing image", exc_info=True)
					return

				post_id_rpc = models.Post.get_next_id_async()

				current_user = users.get_current_user()
				current_user_admin = users.is_current_user_admin()

				post_id = post_id_rpc.get_result()
				post_key = models.Post.get_key(post_id)
				post = models.Post(key=post_key, ip=ip_num)

				post.image = image_key

				post.image_width = image_data.width
				post.image_height = image_data.height
				post.image_url = utils.get_image_url(image_info)

				post_as = self.request.POST.get('post-as', None)

				if current_user:
					post.user = current_user
					if post_as == 'anonymous':
						post.username = 'Anonymous'
					else:
						if current_user_admin and post_as == 'admin':
							post.capcode = "Admin"
						else:
							post.capcode = "Logged in"
						post.username = current_user.nickname()
						if 'post-include-email' in self.request.POST:
							post.email = current_user.email()
				else:
					poster_name = self.request.POST.get('poster-name', '').strip()
					if len(poster_name) > 0:
						post.username = self.request.POST['poster-name']
					else:
						post.username = 'Anonymous'

					if 'poster-email' in self.request.POST:
						post.email = self.request.POST['poster-email']

				if 'post-subject' in self.request.POST:
					post.subject = self.request.POST['post-subject']

				if 'post-comment' in self.request.POST:
					post.comment = utils.format_comment(self.request.POST['post-comment'])

				post.put()

				track_rpc = self.mixpanel_track_async("New thread", {"Post number": post_id, "mp_note": "User made thread #%s." % post_id})

				self.redirect('/post/%s#%s' % (post_id, post_id))

				ndb.Future.wait_all([delete_rpc, track_rpc])
			else:
				index_threads_rpc = models.Post.get_index_page_async()
				delete_rpc = self._delete_files_async()

				logging.info("Banned user attempted to post")

				self.render_response("index.html", threads=index_threads_rpc.get_result())

				delete_rpc.wait()
	def _validate_form(self):
		errors = []

		if not config.DEV_SERVER and self.request.remote_addr != "0.1.0.30":
			logging.warn("Attempted to POST directly to the new thread page")
			errors.append("Obscure error #1")

		if 'post-comment' not in self.request.POST or len(self.request.POST['post-comment'].strip()) <= 0:
			errors.append("You must enter a comment.")

		if len(self.get_uploads()) <= 0:
			errors.append("You must upload an image.")

		return errors

class NewPostPage(BaseUploadHandler):
	@ndb.toplevel
	def post(self, post_id_str, ip_num_str):
		post_id = int(post_id_str)

		main_post_key = models.Post.get_key(post_id)

		main_post = main_post_key.get()

		if main_post and main_post.parent_thread is None:
			errors = self._validate_form()

			if len(errors) > 0:
				delete_rpc = self._delete_files_async()
				child_posts_rpc = models.Post.get_child_posts_async(main_post_key)

				self.render_response("post_view.html", post_errors=errors, main_post=main_post, posts=child_posts_rpc.get_result())

				delete_rpc.wait()
			else:
				ip_num = int(ip_num_str)
				ip = ipaddr.IPAddress(ip_num)

				ban_rpc = self.user_is_banned_async(ip)

				if not ban_rpc.get_result()[0]:
					uploads = self.get_uploads()
					if len(uploads) > 0:
						image_info = self.get_uploads()[0]
						image_key = image_info.key()

						delete_rpc = self._delete_files_async(image_info)

						if image_info.size > config.MAX_FILE_SIZE_BYTES:
							child_posts_rpc = models.Post.get_child_posts_async(main_post_key)
							blobstore.delete(image_key)
							self.render_response("post_view.html", post_errors=['The supplied file was too large.'], main_post=main_post, posts=child_posts_rpc.get_result())
							logging.info("File was too large")
							delete_rpc.wait()
							return

						data = blobstore.fetch_data(image_key, 0, 50000)
						try:
							image_data = images.Image(image_data=data)
							_ = image_data.width
							_ = image_data.height
						except images.NotImageError:
							child_posts_rpc = models.Post.get_child_posts_async(main_post_key)
							blobstore.delete(image_key)
							self.render_response("post_view.html", post_errors=['The supplied file was not an image.'], main_post=main_post, posts=child_posts_rpc.get_result())
							logging.info("Not an image", exc_info=True)
							delete_rpc.wait()
							return
						except images.Error:
							child_posts_rpc = models.Post.get_child_posts_async(main_post_key)
							blobstore.delete(image_key)
							self.render_response("post_view.html", post_errors=['An unknown error occurred when we attempted to process the file you supplied.'], main_post=main_post, posts=child_posts_rpc.get_result())
							logging.warn("Unknown error when processing image", exc_info=True)
							delete_rpc.wait()
							return
					else:
						image_data = None
						image_info = None
						image_key = None
						delete_rpc = None

					main_post_changed = False

					post_id_rpc = models.Post.get_next_id_async()

					current_user = users.get_current_user()
					current_user_admin = users.is_current_user_admin()

					post_id = post_id_rpc.get_result()
					post_key = models.Post.get_key(post_id)
					post = models.Post(key=post_key, ip=ip_num)

					post.parent_thread = main_post_key
					post.thread_bumped = None

					if image_key and image_data and image_info:
						post.image = image_key

						post.image_width = image_data.width
						post.image_height = image_data.height
						post.image_url = utils.get_image_url(image_info)

					post_as = self.request.POST.get('post-as', None)

					if current_user:
						post.user = current_user
						if post_as == 'anonymous':
							post.username = 'Anonymous'
						else:
							if current_user_admin and post_as == 'admin':
								post.capcode = "Admin"
							else:
								post.capcode = "Logged in"
							post.username = current_user.nickname()
							if 'post-include-email' in self.request.POST:
								post.email = current_user.email()
					else:
						poster_name = self.request.POST.get('poster-name', '').strip()
						if len(poster_name) > 0:
							post.username = poster_name
						else:
							post.username = 'Anonymous'

						if 'poster-email' in self.request.POST:
							post.email = self.request.POST['poster-email']

					if 'dont-bump' not in self.request.POST:
						main_post.thread_bumped = datetime.now()
						main_post_changed = True

					if 'post-subject' in self.request.POST:
						post.subject = cgi.escape(self.request.POST['post-subject'])

					if 'post-comment' in self.request.POST:
						post.comment = utils.format_comment(self.request.POST['post-comment'])

					if main_post_changed:
						ndb.put_multi([main_post, post])
					else:
						post.put()

					track_rpc = self.mixpanel_track_async("New thread", {"Post number": post_id, "mp_note": "User made post #%s." % post_id})

					self.redirect('/post/%s#%s' % (main_post_key.id(), post_id))

					if delete_rpc:
						ndb.Future.wait_all([delete_rpc, track_rpc])
					else:
						track_rpc.wait()
				else:
					child_posts_rpc = models.Post.get_child_posts_async(main_post_key)
					delete_rpc = self._delete_files_async()

					self.render_response("post_view.html", main_post=main_post, posts=child_posts_rpc.get_result())

					delete_rpc.wait()
		else:
			delete_rpc = self._delete_files_async()

			self.abort(404)

			delete_rpc.wait()

	def _validate_form(self):
		errors = []

		if not config.DEV_SERVER and self.request.remote_addr != "0.1.0.30":
			logging.warn("Attempted to POST directly to the reply page")
			errors.append("Obscure error #1")

		if ('post-comment' not in self.request.POST or len(self.request.POST['post-comment'].strip()) <= 0) and len(self.get_uploads()) <= 0:
			#errors.append("You must either enter a comment or supply an image.")
			errors.append("You must either enter a comment or supply an image.")

		return errors