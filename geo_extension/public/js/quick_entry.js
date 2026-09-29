// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

/**
 * Geo Extension - quick-entry dialogs.
 *
 * Quick-entry forms (Address quick entry, ERPNext's Customer/Supplier quick
 * entry with address fields, and any other QuickEntryForm subclass) do not run
 * doctype client scripts. This file patches QuickEntryForm.render_dialog so
 * every dialog that has a country field and at least one address level field
 * gets the same cascading selector as the Address form
 * (frappe.geo_extension.attach_to_field_group).
 *
 * Nothing is changed for dialogs without those fields.
 */

(function () {
	if (!window.frappe || !frappe.ui || !frappe.ui.form || !frappe.ui.form.QuickEntryForm) return;
	if (frappe.ui.form.QuickEntryForm.__geo_extension_patched) return;
	frappe.ui.form.QuickEntryForm.__geo_extension_patched = true;

	const original_render = frappe.ui.form.QuickEntryForm.prototype.render_dialog;
	frappe.ui.form.QuickEntryForm.prototype.render_dialog = function () {
		const result = original_render.apply(this, arguments);
		try {
			if (frappe.geo_extension && frappe.geo_extension.attach_to_field_group)
				frappe.geo_extension.attach_to_field_group(this.dialog || this);
		} catch (e) {
			console.error("geo_extension: could not attach to quick entry", e); // eslint-disable-line no-console
		}
		return result;
	};
})();
