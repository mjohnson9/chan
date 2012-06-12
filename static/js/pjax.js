$(function() {
	$('a:not([data-no-pjax])').pjax('#main-content');

	var loading_message_timeout;

	var show_loading_message = function() {
		$("#page-notification").text("Loading...").show();
	};

	var hide_loading_message = function() {
		$("#page-notification").hide();
		if(loading_message_timeout !== null) {
			clearTimeout(loading_message_timeout);
			loading_message_timeout = null;
		}
	};

	$("#main-content").live("pjax:start", function() {
		hide_loading_message();
		loading_message_timeout = setTimeout(show_loading_message, 250);
	}).live("pjax:end", function() {
		hide_loading_message();
	});
});

function change_selected_tab(name) {
	$(".navbar .nav .active[data-nav-name]").removeClass("active");
	if(name !== null) {
		$('.navbar .nav li[data-nav-name="' + name + '"]').addClass("active");
	}
}