frappe.ui.form.on("Address", {
	async setup(frm) {
		// Ensure it reacts properly when the form loads or country changes
		frm.trigger("country");
	},

	async country(frm) {
		reset_fields(frm);
		if (!frm.doc.country) return;

		// Load levels based on Address.country -> Country.code -> matching folder
		const levels = await call("geo_extension.geo_extension.locations.get_levels", {
			country: frm.doc.country,
		});
		frm._levels = levels;

		// Relabel and show only the fields used by this country; clear options
		for (const lvl of levels) {
			frm.set_df_property(lvl.target_field, "label", lvl.label);
			frm.toggle_display(lvl.target_field, true);
			frm.set_df_property(lvl.target_field, "options", "\n");
			frm.set_value(lvl.target_field, "");
		}

		// Populate Level 1
		const root = await call("geo_extension.geo_extension.locations.get_level_options", {
			country: frm.doc.country,
			level_index: 1,
		});
		set_options(frm, levels[0].target_field, root);
	},

	async state(frm) {
		await next_level(frm, "state");
	},
	async county(frm) {
		await next_level(frm, "county");
	},
	async city(frm) {
		await next_level(frm, "city");
	},
	async barangay(frm) {
		await next_level(frm, "barangay");
	},
});

// ----- helpers -----

async function next_level(frm, changed_field) {
	const levels = frm._levels || [];
	const idx = levels.findIndex((l) => l.target_field === changed_field);
	if (idx === -1) return;

	// Clear all lower levels
	for (let i = idx + 1; i < levels.length; i++) {
		const f = levels[i].target_field;
		frm.set_value(f, "");
		frm.set_df_property(f, "options", "\n");
	}

	const next = levels[idx + 1];
	if (!next) return;

	const parent_code = extract_code(frm.doc[changed_field]);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2, // next level (1-based)
		parent_code, // exact match, no case normalization
	});
	set_options(frm, next.target_field, rows);
}

function set_options(frm, fieldname, rows) {
	// Users see "Name (CODE)" for clarity; the saved value in the field is the full string
	const opts = [""].concat(rows.map((r) => `${r.label} (${r.value})`)).join("\n");
	frm.set_df_property(fieldname, "options", opts);
	frm.refresh_field(fieldname);
}

function extract_code(val) {
	if (!val) return "";
	const m = String(val).match(/\(([^)]+)\)\s*$/);
	return m ? m[1] : String(val).trim();
}

function reset_fields(frm) {
	// Hide and clear all known hierarchy fields; the manifest will re-show the needed ones
	["state", "county", "city", "barangay"].forEach((f) => {
		if (frm.fields_dict[f]) {
			frm.toggle_display(f, false);
			frm.set_value(f, "");
			frm.set_df_property(f, "options", "\n");
		}
	});
}

function call(method, args) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (r) => resolve(r.message || []), error: reject });
	});
}
