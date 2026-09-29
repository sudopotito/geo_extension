// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

/**
 * Geo Extension - Address DocType integration.
 *
 * All geographic logic lives in geo_selector.js (frappe.geo_extension). This
 * file only wires it to the native Address form:
 *
 * - Country is moved right below Address Type so it is chosen first, and the
 *   level fields are ordered top-down per the country's hierarchy (pure DOM
 *   reordering; nothing is persisted, nothing is hidden).
 * - Level fields get country-specific labels and suggestion dropdowns.
 * - Changing Country clears the level values and rebuilds the cascade.
 * - Everything stays editable: unsupported countries and free text behave
 *   exactly like native Frappe.
 */

const GEO_LEVEL_FIELDS = ["state", "county", "city", "address_line2"];
const GEO_NATIVE_ORDER = ["address_line2", "city", "county", "state"];

frappe.ui.form.on("Address", {
	onload_post_render(frm) {
		geo_setup(frm);
	},

	refresh(frm) {
		// the form object is shared by every Address opened in the session and
		// onload_post_render runs once per document: rebuild when the document changed
		if (frm._geo && frm._geo.docname !== frm.docname) geo_setup(frm);
	},

	async country(frm) {
		await geo_clear_levels(frm);
		geo_setup(frm);
	},

	state(frm) {
		geo_level_changed(frm, "state");
	},
	county(frm) {
		geo_level_changed(frm, "county");
	},
	city(frm) {
		geo_level_changed(frm, "city");
	},
	address_line2(frm) {
		geo_level_changed(frm, "address_line2");
	},
});

/**
 * A different country means a different hierarchy: clear the level values
 * (and a postal code the app filled in) before rebuilding. Runs with the
 * previous cascade torn down so the clears do not cascade again.
 */
async function geo_clear_levels(frm) {
	const old = frm._geo && frm._geo.cascade;
	if (old) {
		await old.clear_values(); // its levels and an auto-filled postal code
		old.teardown();
	}
	frm._geo = null;
	// address_line2 is street-level text in most countries: only cleared above when a cascade used it
	for (const fieldname of ["state", "county", "city"]) {
		if (frm.fields_dict[fieldname] && frm.doc[fieldname]) await frm.set_value(fieldname, "");
	}
}

async function geo_setup(frm) {
	if (!frappe.geo_extension || !frappe.geo_extension.GeoCascade) return;

	if (frm._geo && frm._geo.cascade) frm._geo.cascade.teardown();

	const cascade = new frappe.geo_extension.GeoCascade({
		country: frm.doc.country,
		adapter: new frappe.geo_extension.FormAdapter(frm),
	});
	frm._geo = { cascade, docname: frm.docname };

	if (frm.doc.country) await cascade.setup();
	if (frm._geo.cascade !== cascade) return; // superseded by a newer country change

	geo_arrange_fields(frm, cascade.supported ? cascade.level_fields : []);
}

function geo_level_changed(frm, fieldname) {
	const cascade = frm._geo && frm._geo.cascade;
	if (cascade && cascade.handles(fieldname)) cascade.handle_change(fieldname);
}

/**
 * Order the address fields as: address_type, country, address_line1, then the
 * level fields top-down (unused native fields keep their native order), then pincode.
 * Fields are only moved when they share the same column; customized layouts are left alone.
 */
function geo_arrange_fields(frm, level_fields) {
	geo_move_after(frm, "country", "address_type");

	const chain = [];
	if (!level_fields.includes("address_line2")) chain.push("address_line2");
	chain.push(...level_fields.filter((f) => GEO_LEVEL_FIELDS.includes(f)));
	chain.push(...GEO_NATIVE_ORDER.filter((f) => !chain.includes(f)));
	chain.push("pincode");

	let anchor = "address_line1";
	for (const fieldname of chain) {
		if (geo_move_after(frm, fieldname, anchor)) anchor = fieldname;
	}
}

function geo_move_after(frm, fieldname, anchor) {
	const field = frm.fields_dict[fieldname];
	const target = frm.fields_dict[anchor];
	if (!field || !target || !field.$wrapper || !target.$wrapper) return false;
	const $a = field.$wrapper;
	const $b = target.$wrapper;
	if (!$a.length || !$b.length || $a.get(0) === $b.get(0)) return false;
	if ($a.parent().get(0) !== $b.parent().get(0)) return false;
	if ($b.next().get(0) !== $a.get(0)) $a.insertAfter($b);
	return true;
}
