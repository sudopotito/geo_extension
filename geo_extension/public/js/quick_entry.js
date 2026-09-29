// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

/**
 * Geo Extension - quick-entry dialogs.
 *
 * Quick-entry forms (Address quick entry, ERPNext's Customer/Supplier quick
 * entry with address fields, and any other QuickEntryForm subclass) do not run
 * doctype client scripts. This file patches QuickEntryForm.render_dialog so
 * every dialog that has a country field and at least one address level field
 * gets the same cascading selector as the Address form.
 *
 * Nothing is changed for dialogs without those fields.
 */

(function () {
	if (!window.frappe || !frappe.ui || !frappe.ui.form || !frappe.ui.form.QuickEntryForm) return;
	if (frappe.ui.form.QuickEntryForm.__geo_extension_patched) return;
	frappe.ui.form.QuickEntryForm.__geo_extension_patched = true;

	// ERPNext's contact/address quick entry names the country field "country_address"
	const COUNTRY_FIELDS = ["country", "country_address"];
	const LEVEL_FIELDS = ["state", "county", "city", "address_line2"];

	class DialogAdapter {
		constructor(dialog) {
			this.dialog = dialog;
			this.original_labels = {};
		}
		field(fieldname) {
			return this.dialog.fields_dict && this.dialog.fields_dict[fieldname];
		}
		has_field(fieldname) {
			return !!this.field(fieldname);
		}
		get_value(fieldname) {
			return this.dialog.get_value(fieldname);
		}
		set_value(fieldname, value) {
			return Promise.resolve(this.dialog.set_value(fieldname, value));
		}
		get_input(fieldname) {
			const ctrl = this.field(fieldname);
			return ctrl && ctrl.$input ? ctrl.$input.get(0) : null;
		}
		set_label(fieldname, label) {
			const ctrl = this.field(fieldname);
			if (!ctrl || typeof ctrl.set_label !== "function") return;
			if (!(fieldname in this.original_labels)) this.original_labels[fieldname] = ctrl.df.label;
			ctrl.set_label(label);
		}
		restore_label(fieldname) {
			const ctrl = this.field(fieldname);
			if (ctrl && fieldname in this.original_labels) ctrl.set_label(this.original_labels[fieldname]);
		}
		attach_suggestions(fieldname, provider) {
			frappe.geo_extension.attach_suggestions(this.get_input(fieldname), provider);
		}
		detach_suggestions(fieldname) {
			frappe.geo_extension.detach_suggestions(this.get_input(fieldname));
		}
	}

	function on_change(dialog, fieldname, handler) {
		const ctrl = dialog.fields_dict[fieldname];
		if (!ctrl) return;
		const df = ctrl.df;
		const previous = df.change || df.onchange;
		df.change = function () {
			const result = previous ? previous.apply(this, arguments) : undefined;
			handler();
			return result;
		};
	}

	function attach(dialog) {
		if (!frappe.geo_extension || !frappe.geo_extension.GeoCascade || dialog.__geo_cascade) return;
		const country_field = COUNTRY_FIELDS.find((f) => dialog.fields_dict && dialog.fields_dict[f]);
		if (!country_field) return;
		if (!LEVEL_FIELDS.some((f) => dialog.fields_dict[f])) return;

		const adapter = new DialogAdapter(dialog);
		const state = { cascade: null };
		dialog.__geo_cascade = state;

		const setup = async () => {
			if (state.cascade) state.cascade.teardown();
			const cascade = new frappe.geo_extension.GeoCascade({
				country: dialog.get_value(country_field),
				adapter,
			});
			state.cascade = cascade;
			if (dialog.get_value(country_field)) await cascade.setup();
		};

		on_change(dialog, country_field, async () => {
			const old = state.cascade;
			if (old) {
				const fields = new Set(LEVEL_FIELDS.filter((f) => f !== "address_line2"));
				old.level_fields.forEach((f) => fields.add(f));
				const auto = old.auto_postal;
				old.teardown();
				state.cascade = null;
				if (auto && dialog.get_value("pincode") === auto) await adapter.set_value("pincode", "");
				for (const f of fields) {
					if (dialog.fields_dict[f] && dialog.get_value(f)) await adapter.set_value(f, "");
				}
			}
			await setup();
		});
		for (const f of LEVEL_FIELDS) {
			if (!dialog.fields_dict[f]) continue;
			on_change(dialog, f, () => {
				if (state.cascade && state.cascade.handles(f)) state.cascade.handle_change(f);
			});
		}
		setup();
	}

	const original_render = frappe.ui.form.QuickEntryForm.prototype.render_dialog;
	frappe.ui.form.QuickEntryForm.prototype.render_dialog = function () {
		const result = original_render.apply(this, arguments);
		try {
			attach(this.dialog || this);
		} catch (e) {
			console.error("geo_extension: could not attach to quick entry", e); // eslint-disable-line no-console
		}
		return result;
	};

	frappe.geo_extension.DialogAdapter = DialogAdapter;
	frappe.geo_extension.attach_to_dialog = attach;
})();
