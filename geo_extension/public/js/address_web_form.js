// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

/**
 * Geo Extension - Address Web Forms (website / portal).
 *
 * Included through hooks.webform_include_js for standard Web Forms on Address
 * (for example ERPNext's portal "Addresses" form at /address) together with
 * geo_selector.js. frappe.web_form is a FieldGroup, so the same wiring as
 * quick-entry dialogs applies: country-specific labels, suggestions per level
 * and postal codes; free text is still accepted.
 *
 * Custom (non-standard) Web Forms can do the same from their client script:
 *
 *   frappe.require("/assets/geo_extension/js/geo_selector.js", () =>
 *       frappe.geo_extension.attach_to_field_group(frappe.web_form));
 */

frappe.ready(function () {
	const web_form = window.frappe && frappe.web_form;
	if (!web_form || !web_form.fields_dict) return; // list view or not a form
	if (!frappe.geo_extension || !frappe.geo_extension.attach_to_field_group) return;
	try {
		frappe.geo_extension.attach_to_field_group(web_form);
	} catch (e) {
		console.error("geo_extension: could not attach to web form", e); // eslint-disable-line no-console
	}
});
