import config

class Template(object):
	def render(self):
		raise NotImplementedError("You must override render in your template.")

class Header(Template):
	def render(self):
		return "<!DOCTYPE html>"\
		       "<html>"\
		       "<head>"\
		       "<title>chan</title>"\
		       "<link rel=\"stylesheet\" href=\"/static/%s/css/bootstrap.css\"/>"\
		       "<link rel=\"stylesheet\" href=\"/static/%s/css/bootstrap-responsive.css\"/>"\
		       "<link rel=\"stylesheet\" href=\"/static/%s/css/chan.css\"/>"\
		       "<script type=\"text/javascript\" src=\"https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.js\"></script>"\
		       "<script type=\"text/javascript\" src=\"/static/%s/js/bootstrap.js\"></script>"\
		       "</head>"\
		       "<body>" \
		       "<div class=\"container\">" % (config.VERSION_ID, config.VERSION_ID, config.VERSION_ID, config.VERSION_ID)

class Footer(Template):
	def render(self):
		return "</div>" \
		       "</body>"\
		       "</html>"

class Navbar(Template):
	def _render_menu_items(self, items, current_page):
		items_str = ""

		for id, display_name, link, subitems in items:
			if subitems is None:
				if id is not None and current_page == id:
					items_str += "<li class=\"active\"><a href=\"%s\">%s</a></li>" % (link, display_name)
				else:
					items_str += "<li><a href=\"%s\">%s</a></li>" % (link, display_name)
			else:
				items_str += "<li class=\"dropdown\">" \
				             "<a class=\"dropdown-toggle\" data-toggle=\"dropdown\">%s<b class=\"caret\"></b></a>" \
				             "<ul class=\"dropdown-menu\">" % display_name

				items_str += self._render_menu_items(items=subitems, current_page=None)

				items_str += "</ul>"

		return items_str

	def render(self, user, is_admin, current_page=None):
		navbar = "<div class=\"navbar navbar-fixed-top\">" \
		         "<div class=\"navbar-inner\">" \
		         "<div class=\"container\">" \
		         "<a class=\"brand\">chan</a>" \
		         "<ul class=\"nav\">"

		navbar_items_left = [
			("home", "Home", "/", None)
		]

		navbar_items_right = []

		navbar += self._render_menu_items(items=navbar_items_left, current_page=current_page)

		navbar += "</ul>" \
		          "<ul class=\"nav pull-right\">"

		if is_admin:
			navbar_items_right.append(("admin", "Admin", None, [
				("admin-ban", "Ban", "/admin/ban", None)
			]))

		if user:
			navbar_items_right.append(("logout", "Logout", "/logout", None))
		else:
			navbar_items_right.append(("login", "Login", "/login", None))

		navbar += self._render_menu_items(items=navbar_items_right, current_page=current_page)

		navbar += "</ul>"

		navbar += "</div></div></div>"

		return navbar

class Post(Template):
	def render(self, post, is_admin, thread=False):
		post_id = post.key.id()

		if post.parent_thread:
			main_post_id = post.parent_thread.id()
		else:
			main_post_id = post_id

		post_str = "<div class=\"row\">"

		if post.image:
			post_str += "<div class=\"span3\">" \
			            "<a class=\"thumbnail\" href=\"%s=s%s\">" \
			            "<img src=\"%s=s260\" alt=\"Thread image\" title=\"Original size: %sx%s\"/>" \
			            "</a>" \
			            "</div>" % (post.image_url, max(post.image_height, post.image_width), post.image_url, post.image_width, post.image_height)

		post_str += "<div class=\"span9\">"

		if post.subject:
			post_str += "<span class=\"post-subject\">%s</span>" % post.subject

		post_str += "<span class=\"user-info\""

		if post.capcode:
			post_str += " data-capcode=\"%s\"" % post.capcode.lower()

		post_str += ">"

		if post.email:
			post_str += "<a href=\"mailto:%s\">" % post.email

		post_str += "<span class=\"username\">%s</span>" % post.username

		if post.email:
			post_str += "</a>"

		if post.capcode:
			post_str += "<span class=\"capcode\">%s</span>" % post.capcode

		post_str += "</span>" \
		            "<span class=\"posted\">%s</span>" \
		            "<span class=\"post-number\">%s</span>" \
		            "<div class=\"thread-toolbar btn-toolbar\">" \
		            "<div class=\"btn-group\">" \
		            "<a class=\"btn btn-mini\" href=\"/post/%s?comment=>>%s#post\"><i class=\"icon-comment\"></i>&nbsp;Reply</a>" \
		            "<a class=\"btn btn-mini\" href=\"/post/%s#%s\">Permalink</a>" \
		            "</div>" % (post.posted_string, post_id, main_post_id, post_id, main_post_id, post_id)

		if is_admin:
			post_str += "<div class=\"btn-group\" id=\"admin-menu-%s\">" \
			            "<a class=\"btn btn-mini dropdown-toggle\" data-toggle=\"dropdown\" href=\"#admin-menu-%s\"><i class=\"icon-user\"></i>&nbsp;Admin<b class=\"caret\"></b></a>" \
			            "<ul class=\"dropdown-menu\">" \
			            "<li><a href=\"/admin/post/%s/delete\"><i class=\"icon-trash\"></i>&nbsp;Delete</a></li>" \
			            "<li><a href=\"/admin/post/%s/ban\"><i class=\"icon-ban-circle\"></i>&nbsp;Ban</a></li>" \
			            "<li><a href=\"/admin/post/%s/bandelete\"><i class=\"icon-exclamation-sign\"></i>&nbsp;Ban &amp; delete</a></li>" \
			            "<li class=\"divider\"></li>" \
			            "<li><a>IP address: %s</a></li>" \
			            "</ul>" \
			            "</div>" % (post_id, post_id, post_id, post_id, post_id, post.ip_string)

		post_str += "</div>"

		if post.comment:
			post_str += "<p class=\"well post-comment\">%s</p>" % post.comment

		if thread:
			post_str += "<p>All replies are omitted. Click reply to view.</p>"

		post_str += "</div></div>"

		return post_str

class Banned(Template):
	def render(self, ip, ban_reason):
		return "<div class=\"alert alert-error\">" \
		       "Your IP (%s) has been banned. The listed reason is:" \
		       "<div class=\"ban-reason\">%s</div>" \
		       "While banned you may view posts but may not post." \
		       "</div>" % (ip, ban_reason)

class PostForm(Template):
	def __init__(self):
		self._banned = Banned()

	def render(self, form_title, upload_url, ip, banned, ban_reason, user, is_admin, errors=None):
		if banned:
			return self._banned.render(ip=ip, ban_reason=ban_reason)
		else:
			post_form = "<form class=\"post-form form-horizontal\" enctype=\"multipart/form-data\" method=\"POST\" action=\"%s\">" \
			            "<a id=\"post\"></a>" \
			            "<input type=\"hidden\" name=\"MAX_FILE_SIZE\" value=\"%s\"/>" % (upload_url, config.MAX_FILE_SIZE_BYTES)

			if errors is not None:
				for error in errors:
					post_form += "<div class=\"alert alert-error\">%s</div>" % error

			post_form += "<fieldset>" \
			             "<legend>%s</legend>" \
			             "<div class=\"control-group\">" \
			             "<label class=\"control-label\" for=\"poster-name\">Name</label>" \
			             "<div class=\"controls\">" % form_title

			if user:
				post_form += "<input type=\"text\" class=\"input-xlarge disabled\" id=\"poster-name\" name=\"poster-name\" disabled=\"disabled\" value=\"%s\"/>" \
				             "<label class=\"radio\"><input type=\"radio\" name=\"post-as\" id=\"post-as-anon\" value=\"anonymous\"/> Post as Anonymous</label>" \
				             "<label class=\"radio\"><input type=\"radio\" name=\"post-as\" id=\"post-as-logged-in\" value=\"user\" checked/> Post as a logged in user</label>" % user.nickname()

				if is_admin:
					post_form += "<label class=\"radio\"><input type=\"radio\" name=\"post-as\" id=\"post-as-admin\" value=\"admin\"/> Post as an administrator</label>"
			else:
				post_form += "<input type=\"text\" class=\"input-xlarge\" id=\"poster-name\" name=\"poster-name\"/>"

			post_form += "<p class=\"help-block\">The name to show on the post. It can include tripcodes (not currently implemented). If left blank, it will be Anonymous. Secure tripcodes will not work. Instead, you may use the login button in the upper-right.</p>" \
			             "</div>" \
			             "</div>"

			post_form += "<"


			post_form += "</fieldset>"

			post_form += "</form>"

			return post_form

class Index(Template):
	def __init__(self):
		self._header = Header()
		self._navbar = Navbar()
		self._post_form = PostForm()
		self._post = Post()
		self._footer = Footer()

	def render(self, threads, ip, user, is_admin, upload_url=None, banned=False, ban_reason=None):
		index_page = self._header.render()

		index_page += self._navbar.render(current_page="home", user=user, is_admin=is_admin)

		index_page += self._post_form.render(form_title="New thread", upload_url=upload_url, ip=ip, banned=banned, ban_reason=ban_reason, user=user, is_admin=is_admin)

		for thread in threads:
			index_page += self._post.render(post=thread, is_admin=is_admin, thread=True)

		index_page += self._footer.render()
		return index_page