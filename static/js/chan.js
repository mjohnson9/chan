// ==ClosureCompiler==
// @compilation_level ADVANCED_OPTIMIZATIONS
// @output_file_name chan.min.js
// @use_closure_library true
// @code_url https://ajax.googleapis.com/ajax/libs/jquery/1.7.2/jquery.js
// @code_url http://chan.nightexcessive.us/static/1/js/bootstrap.js
// ==/ClosureCompiler==

goog.require("goog.net.Cookies");

goog.require("goog.events");

goog.require("goog.dom");

goog.provide("nightexcessive.chan");


/**
 * The class for the entirety of the chan functionality.
 * @constructor
 */
nightexcessive.chan = function() {
	/**
	 * The cookie manager for this chan.
	 * @type {!goog.net.Cookies}
	 * @private
	 */
	this._cookies = new goog.net.Cookies(document);

	/**
	 * The element for the theme selector menu.
	 * @type {!Element}
	 * @private
	 */
	this._themeMenu = goog.dom.getElement("themeselector-menu");

	var currentTheme = this.getCurrentTheme();

	for(var i = 0; i < this._themeMenu.children.length; i++) {
		var child = this._themeMenu.children[i];

		goog.events.listen(child, goog.events.EventType.CLICK, this._themeChangeClicked);
	}

	this.setTheme(currentTheme, false);

	/**
	 * The element that holds all displayed messages.
	 * @type {!Element}
	 * @private
	 */
	this._messages = goog.dom.getElement("messages");

	if(!this._cookies.isEnabled()) {
		this.displayMessage("You must have cookies enabled for this site to work properly.", "Cookies", nightexcessive.chan.MessageType.WARN, false);
	} else {
		var desiredTheme = this._cookies.get("theme", null);

		if(desiredTheme !== null) {
			this.setTheme(desiredTheme);
		} else {
			var oldDesiredTheme = this._cookies.get("style", null);

			if(oldDesiredTheme !== null) {
				this.setTheme(oldDesiredTheme);
			}
		}
	}
};

/**
 * Enumerations for message types.
 * @enum {number}
 */
nightexcessive.chan.MessageType = {
	ERROR: 0,
	SUCCESS: 1,
	INFO: 2,
	WARN: 3
};

/**
 * Displays a message at the top of the page.
 * @param {!string} message The message to display.
 * @param {string=} opt_heading The heading for the message.
 * @param {nightexcessive.chan.MessageType=} opt_type The type of message.
 * @param {boolean=} opt_closeButton Whether or not to show the close button.
 */
nightexcessive.chan.prototype.displayMessage = function(message, opt_heading, opt_type, opt_closeButton) {
	var messageDom = goog.dom.createElement("div");
	messageDom.classList.add("alert");

	if(opt_type == nightexcessive.chan.MessageType.ERROR) {
		messageDom.classList.add("alert-error");
	} else if(opt_type == nightexcessive.chan.MessageType.SUCCESS) {
		messageDom.classList.add("alert-success");
	} else if(opt_type == nightexcessive.chan.MessageType.INFO) {
		messageDom.classList.add("alert-info");
	}

	if(opt_closeButton === undefined || !!opt_closeButton) {
		var closeButton = goog.dom.createElement("button");
		closeButton.classList.add("close");
		closeButton.dataset.dismiss = "alert";
		closeButton.href = "#";
		closeButton.innerHTML = "&times;";
		messageDom.appendChild(closeButton);
	}

	if(opt_heading !== undefined) {
		var heading = goog.dom.createElement("strong");
		heading.textContent = opt_heading;
		messageDom.appendChild(heading);
	}

	messageDom.innerHTML += "&nbsp;" + message;

	this._messages.appendChild(messageDom);
};

/**
 * Gets all link tags that qualify as a "theme."
 * @return {Array.<Element>} The qualifying tags.
 * @private
 */
nightexcessive.chan.prototype._getValidThemes = function() {
	var links = goog.dom.getElementsByTagNameAndClass("link");

	var validThemes = [];
	for(var i = 0; i < links.length; i++) {
		var link = links[i];

		var rel = link.rel.toLowerCase();

		var title = link.title;
		if(title) title = title.trim();

		if((rel == "stylesheet" || rel == "alternate stylesheet") && (title && title.length > 0)) {
			validThemes.push(link);
		}
	}

	return validThemes;
};

/**
 * Gets the current theme's title.
 * @return {?string} The current theme's title, or null if none was found.
 */
nightexcessive.chan.prototype.getCurrentTheme = function() {
	var validThemes = this._getValidThemes();

	for(var i = 0; i < validThemes.length; i++) {
		var theme = validThemes[i];

		if(!theme.disabled) {
			return theme.title;
		}
	}

	return null;
};

/**
 * Sets the current theme.
 * @param {!string} title The title of the theme to set to.
 * @param {boolean=} opt_save Whether or not to save this in a cookie.
 */
nightexcessive.chan.prototype.setTheme = function(title, opt_save) {
	var validThemes = this._getValidThemes();

	for(var i = 0; i < validThemes.length; i++) {
		var style = validThemes[i];

		if(style.title == title) {
			style.disabled = false;
		} else {
			style.disabled = true;
		}
	}

	for(var i = 0; i < this._themeMenu.children.length; i++) {
		var child = this._themeMenu.children[i];

		if(child && child.dataset) {
			var themeName = child.dataset.themeName;
			if(themeName == title) {
				child.classList.add("active");
			} else {
				child.classList.remove("active");
			}
		}
	}

	if(opt_save == undefined || !!opt_save) {
		this._cookies.set("theme", title);
	}
};

/**
 * The callback for when a theme change button is clicked.
 * @private
 */
nightexcessive.chan.prototype._themeChangeClicked = function() {
	if(this && this.dataset) {
		var themeName = this.dataset.themeName;
		if(themeName) {
			window.thisChan.setTheme(themeName);
		}
	}
};

/**
 * Called when the page is loaded to initialize everything needed.
 */
nightexcessive.chan.pageLoaded = function() {
	window.thisChan = new nightexcessive.chan();
};

goog.events.listen(window, goog.events.EventType.LOAD, nightexcessive.chan.pageLoaded);