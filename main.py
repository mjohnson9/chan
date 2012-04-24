import webapp2

import config
import views

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