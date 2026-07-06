// Redirects the "AI Education Suite" workspace straight to the custom
// dashboard page, so clicking the sidebar entry never shows the raw
// modules/shortcuts workspace layout to end users.
//
// The Workspace record still exists (it's what makes the sidebar entry
// show up at all, and it's still reachable/editable by admins), but the
// moment anyone actually navigates to it, we immediately reroute.

(function () {
	var TARGET_WORKSPACE_NAMES = [
		"AI Education Suite", "ai-education-suite", "ai education suite",
	];
	var DASHBOARD_ROUTE = "ai-education-dashboard";

	function maybe_redirect() {
		var route = frappe.get_route();
		if (!route || !route.length) return;

		// Workspaces route as a single-segment slug (e.g. ["ai-education-suite"]),
		// same shape as a Page route — there's no "workspace/" prefix segment.
		var first = (route[0] || "").toString();
		var second = (route[1] || "").toString();
		var candidates = [first, second, first.toLowerCase(), second.toLowerCase()];

		if (first === DASHBOARD_ROUTE) return; // already there, avoid any loop

		var is_target = TARGET_WORKSPACE_NAMES.some(function (name) {
			return candidates.indexOf(name) !== -1 || candidates.indexOf(name.toLowerCase()) !== -1;
		});
		if (is_target) {
			frappe.set_route(DASHBOARD_ROUTE);
		}
	}

	$(document).on("app_ready", function () {
		frappe.router.on("change", maybe_redirect);
		// Also check once immediately, in case the app loaded directly on
		// the workspace route (deep link / bookmark / page refresh).
		maybe_redirect();
	});
})();
