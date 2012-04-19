import webapp2
import models
import config
import utils
import logging
import cgi
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import blobstore
from google.appengine.api import images
from google.appengine.ext.webapp import blobstore_handlers

class BaseHandler(webapp2.RequestHandler):
	def render_response(self, _template, **context):
		# Renders a template and writes the result to the response.
		if 'user' not in context:
			current_user = users.get_current_user()
			if current_user:
				context['user'] = current_user

		if 'user_is_admin' not in context:
			context['user_is_admin'] = users.is_current_user_admin()

		template = config.jinja_environment.get_template(_template)
		self.response.write(template.render(context))

class BaseUploadHandler(blobstore_handlers.BlobstoreUploadHandler):
	def render_response(self, _template, **context):
		# Renders a template and writes the result to the response.
		if 'user' not in context:
			current_user = users.get_current_user()
			if current_user:
				context['user'] = current_user
		template = config.jinja_environment.get_template(_template)
		self.response.write(template.render(context))

class IndexPage(BaseHandler):
	@ndb.toplevel
	def get(self):
		index_threads_rpc = models.Thread.get_index_page_async(0)
		upload_url_rpc = blobstore.create_upload_url_async("/new-thread", max_bytes_per_blob=config.MAX_FILE_SIZE_BYTES, max_bytes_total=config.MAX_FILE_SIZE_BYTES)

		index_threads = [i.get_result() for i in index_threads_rpc]
		index_post_keys = [i.main_post for i in index_threads]

		index_posts_rpc = ndb.get_multi_async(index_post_keys)

		finished_index_threads = []

		i = 0
		for post_rpc in index_posts_rpc:
			finished_index_threads.append((index_threads[i], post_rpc.get_result()))
			i += 1

		upload_url = utils.clean_dev_url(upload_url_rpc.get_result())
		self.render_response('index.jade', upload_url=upload_url, threads=finished_index_threads)

class IPPage(BaseHandler):
	@ndb.toplevel
	def get(self):
		self.response.headers['Content-Type'] = 'text/plain'
		self.response.write('remote_addr: %s\n' % self.request.remote_addr)
		self.response.write('headers: %s\n' % self.request.headers)

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
	def post(self):
		errors = self.__validate_form()

		if len(errors) > 0:
			delete_rpc = self.__delete_files_async()

			self.render_response("index.jade", post_errors=errors)

			delete_rpc.wait()
		else:
			image_info = self.get_uploads()[0]
			image_key = image_info.key()

			delete_rpc = self.__delete_files_async(image_info)

			if image_info.size > config.MAX_FILE_SIZE_BYTES:
				blobstore.delete([image_key])
				delete_rpc.wait()
				self.render_response("index.jade", post_errors=['The supplied file was too large.'])
				logging.info("File was too large")
				return

			data = blobstore.fetch_data(image_key, 0, 50000)
			try:
				image_data = images.Image(image_data=data)
				_ = image_data.width
				_ = image_data.height
			except images.NotImageError:
				blobstore.delete([image_key])
				delete_rpc.wait()
				self.render_response("index.jade", post_errors=['The supplied file was not an image.'])
				logging.info("Not an image", exc_info=True)
				return
			except images.Error:
				blobstore.delete([image_key])
				delete_rpc.wait()
				self.render_response("index.jade", post_errors=['An unknown error occurred when we attempted to process the file you supplied.'])
				logging.warn("Unknown error when processing image", exc_info=True)
				return

			current_user = users.get_current_user()
			current_user_admin = users.is_current_user_admin()

			post_key = models.Post.get_key(models.Post.get_next_id())
			post = models.Post(key=post_key, ip=utils.dotted_quad_to_num(self.request.remote_addr))

			thread = models.Thread(main_post=post.key)

			post.parent_thread = thread.key
			post.image = image_key

			post.image_width = image_data.width
			post.image_height = image_data.height
			post.image_url = utils.get_image_url(image_info)

			if current_user:
				post.user = current_user
				if 'post-as-anonymous' in self.request.POST:
					post.username = 'Anonymous'
				else:
					if current_user_admin:
						if 'post-as-admin' in self.request.POST:
							post.capcode = "Admin"
						else:
							post.capcode = "Logged in"
					else:
						post.capcode = "Logged in"
					post.username = current_user.nickname()
					if 'post-include-email' in self.request.POST:
						post.email = current_user.email()
			else:
				if 'poster-name' in self.request.POST:
					poster_name = self.request.POST['poster-name'].strip()
					if len(poster_name) > 0:
						post.username = self.request.POST['poster-name']
					else:
						post.username = 'Anonymous'
				else:
					post.username = 'Anonymous'

				if 'poster-email' in self.request.POST:
					post.email = self.request.POST['poster-email']

			if 'post-subject' in self.request.POST:
				post.subject = self.request.POST['post-subject']

			if 'post-comment' in self.request.POST:
				post.comment = cgi.escape(self.request.POST['post-comment'].strip()).replace("\n", "<br/>\n")

			ndb.put_multi([thread, post])

			#self.redirect('/thread/%s' % thread.key.id())
			self.redirect('/')
			#self.response.headers['Content-Type'] = 'text/plain'
			#self.response.write('remote_addr: %s\n' % self.request.remote_addr)
			#self.response.write('headers: %s\n' % self.request.headers)
			delete_rpc.wait()

	def __delete_files_async(self, exclude=None):
		if not exclude or (type(exclude) == list and len(exclude) <= 0):
			logging.info("Deleting all uploaded files...")
			return blobstore.delete_async(self.get_uploads())
		else:
			files = []
			if type(exclude) != list:
				for file in self.get_uploads():
					if file != exclude:
						files.append(file)
			else:
				for file in self.get_uploads():
					if file not in exclude:
						files.append(file)
			logging.info("Deleting uploaded files: %s", files)
			return blobstore.delete_async(files)

	def __validate_form(self):
		errors = []

		if 'post-comment' not in self.request.POST or len(self.request.POST['post-comment'].strip()) <= 0:
			errors.append("You must either enter a comment.")

		if len(self.get_uploads()) <= 0:
			errors.append("You must upload an image.")

		return errors