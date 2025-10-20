// public/js/address_filters.js
frappe.ui.form.on("Address", {
	async setup(frm) {
		frm._geo = { mode: "freeform", levels: [] }; // 'freeform' | 'guided'
		frm.trigger("country");
	},

	async country(frm) {
		// reset first
		await set_mode_freeform(frm);

		if (!frm.doc.country) return;

		// Try to load manifest/levels; if fails, stay in freeform (Data inputs)
		let levels = [];
		try {
			levels = await call("geo_extension.geo_extension.locations.get_levels", {
				country: frm.doc.country,
			});
		} catch (e) {
			// no manifest / bad config → keep freeform
			return;
		}

		if (!levels || !levels.length) return;

		frm._geo = { mode: "guided", levels };

		// Show only the fields used by this country; do NOT change labels
		const used = new Set(levels.map((l) => l.target_field));
		for (const f of ["state", "county", "city", "barangay"]) {
			if (!frm.fields_dict[f]) continue;
			frm.toggle_display(f, used.has(f));
			// flip to Select for used fields, keep Data for unused (hidden anyway)
			if (used.has(f)) await ensure_fieldtype(frm, f, "Select");
			frm.set_df_property(f, "options", "\n");
			if (!frm.is_new()) frm.refresh_field(f);
		}

		// Load level 1 options
		const root = await call("geo_extension.geo_extension.locations.get_level_options", {
			country: frm.doc.country,
			level_index: 1,
		});
		const firstField = levels[0].target_field;
		set_select_options(frm, firstField, root);
	},

	async state(frm) {
		if (frm._geo.mode === "guided") await next_level(frm, "state");
	},
	async county(frm) {
		if (frm._geo.mode === "guided") await next_level(frm, "county");
	},
	async city(frm) {
		if (frm._geo.mode === "guided") await next_level(frm, "city");
	},
	async barangay(frm) {
		/* last level, nothing to load */
	},
});

// ---- helpers ----

async function next_level(frm, changed_field) {
	const levels = frm._geo.levels || [];
	const idx = levels.findIndex((l) => l.target_field === changed_field);
	if (idx === -1) return;

	// clear downstream
	for (let i = idx + 1; i < levels.length; i++) {
		const f = levels[i].target_field;
		if (frm.fields_dict[f]) {
			frm.set_value(f, "");
			frm.set_df_property(f, "options", "\n");
			await ensure_fieldtype(frm, f, "Select");
			frm.refresh_field(f);
		}
	}

	const next = levels[idx + 1];
	if (!next) return;

	const parent_code = extract_code(frm.doc[changed_field]);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2, // 1-based
		parent_code,
	});
	set_select_options(frm, next.target_field, rows);
}

async function set_mode_freeform(frm) {
	// Show all fields as Data and clear Select options
	frm._geo = { mode: "freeform", levels: [] };
	for (const f of ["state", "county", "city", "barangay"]) {
		if (!frm.fields_dict[f]) continue;
		frm.toggle_display(f, true);
		await ensure_fieldtype(frm, f, "Data");
		frm.set_df_property(f, "options", ""); // irrelevant for Data, just cleaning
		// DO NOT clear user values here to let them keep typing
		frm.refresh_field(f);
	}
}

function set_select_options(frm, fieldname, rows) {
	// Display "Name (CODE)" so it’s clear; underlying stored value is that string
	const opts = [""].concat(rows.map((r) => `${r.label} (${r.value})`)).join("\n");
	frm.set_df_property(fieldname, "options", opts);
	frm.refresh_field(fieldname);

	// If the user already typed something (freeform → guided), keep it by appending
	const current = frm.doc[fieldname];
	if (current && !opts.includes(current)) {
		const appended = opts + "\n" + current;
		frm.set_df_property(fieldname, "options", appended);
		frm.refresh_field(fieldname);
	}
}

function extract_code(val) {
	if (!val) return "";
	const m = String(val).match(/\(([^)]+)\)\s*$/);
	return m ? m[1] : String(val).trim();
}

async function ensure_fieldtype(frm, fieldname, targetType) {
	const df = frm.fields_dict[fieldname]?.df;
	if (!df || df.fieldtype === targetType) return;
	// Client-side switch: affects UI only; DB schema remains the same field
	frm.set_df_property(fieldname, "fieldtype", targetType);
}

function call(method, args) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (r) => resolve(r.message || []), error: reject });
	});
}
