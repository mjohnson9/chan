import logging
import os
import webapp2

import config
import views

class ErrorHandler(object):
	class Contents(object):
		NOT_FOUND_PATH = os.path.join("static", "errors", "404.html")

		NOT_FOUND_FILE = open(NOT_FOUND_PATH, "r")
		NOT_FOUND = NOT_FOUND_FILE.read()
		NOT_FOUND_FILE.close()

	@classmethod
	def page_not_found(cls, request, response, exception):
		logging.debug("404 handler called", exc_info=exception)
		response.write(cls.Contents.NOT_FOUND)
		response.set_status(404)

app = webapp2.WSGIApplication([
                               ('/', views.IndexPage),
                               ('/new-thread/(.+)', views.NewThreadPage),
                               ('/login', views.LoginPage),
                               ('/logout', views.LogoutPage),
                               ('/post/(\d+)', views.PostPage),
                               ('/post/(\d+)/reply/(.+)', views.NewPostPage),
                               ('/image/(\d+)', views.ImagePage),
                               ('/admin/post/(\d+)/ban(delete)?', views.BanPage),
                               ('/admin/ban', views.BanPage)
                              ], debug=config.DEV_MODE)
app.error_handlers[404] = ErrorHandler.page_not_found