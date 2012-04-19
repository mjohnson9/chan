import webapp2
import config
import views

app = webapp2.WSGIApplication([
                               ('/', views.IndexPage),
                               ('/ip', views.IPPage),
                               ('/new-thread', views.NewThreadPage),
                               ('/login', views.LoginPage),
                               ('/logout', views.LogoutPage)
                              ], debug=config.DEV_MODE)