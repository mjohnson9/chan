(function(d, c) {
	var a, b, g, e;

	a = d.createElement("script");
	a.type = "text/javascript";
	a.async = !0;
	a.src = ("https:" === d.location.protocol ? "https:" : "http:") + '//api.mixpanel.com/site_media/js/api/mixpanel.2.js';

	b = d.getElementsByTagName("script")[0];
	b.parentNode.insertBefore(a, b);

	c._i = [];
	c.init = function(a,d,f) {
		var b = c;
		typeof f !== "undefined" ? b = c[f] = [] : f = "mixpanel";
		g = "disable track track_pageview track_links track_forms register register_once unregister identify name_tag set_config".split(" ");
		for(e = 0; e < g.length; e++)(
			function(a) {
				b[a] = function() {
					b.push([a].concat(Array.prototype.slice.call(arguments,0)))
				}
			}
		)(g[e]);
		c._i.push([a,d,f]);
	};

	window.mixpanel = c;
})(document, []);

mixpanel.init("136b8dd37612f44384a87565c3d7de36");
if($.cookie("mixpanel-uuid") !== null) {
	mixpanel.identify($.cookie("mixpanel-uuid"));
	console.log("Identified with", $.cookie("mixpanel-uuid"));
}