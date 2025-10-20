const LEVEL_FIELDS = ["state", "county", "city", "barangay"];

/**
 * Behavior:
 * - If a manifest exists for the selected country:
 *   * Show only the target fields listed there
 *   * Feed Autocomplete with LABELS ONLY (e.g., "Quezon City")
 *   * Maintain a label->code map per field so cascading uses correct parent_code
 * - If no manifest exists:
 *   * Keep default layout/order and show all fields (freeform typing)
 * - On COUNTRY CHANGE (or clear):
 *   * Clear BOTH values and options of all level fields, and reset the map
 */
frappe.ui.form.on("Address", {
	async onload_post_render(frm) {
		frm._geo = { mode: "freeform", levels: [], _init: false, map: {} };
		await frm.trigger("country");
	},

	async refresh(frm) {
		if (!frm._geo?._init && frm.doc.country) {
			frm._geo._init = true;
			await frm.trigger("country");
		}
	},

	async country(frm) {
		// Country changed/cleared → nuke downstream values and options, reset map
		clear_levels(frm); // <-- clears values + options + map
		await set_mode_freeform(frm); // <-- shows all; empty suggestions

		if (!frm.doc.country) return; // if cleared, stop here (freeform blank)

		// Try to load manifest; if none, stay freeform
		let levels = [];
		try {
			levels =
				(await call("geo_extension.geo_extension.locations.get_levels", {
					country: frm.doc.country,
				})) || [];
		} catch {
			return;
		}
		if (!levels.length) return;

		frm._geo = { mode: "guided", levels, _init: true, map: {} };

		// Show only fields present in manifest; clear options for used fields
		const used = new Set(levels.map((l) => l.target_field));
		for (const f of LEVEL_FIELDS) {
			if (!frm.fields_dict[f]) continue;
			frm.toggle_display(f, used.has(f));
			if (used.has(f)) set_ac_options(frm, f, []); // start fresh
		}

		// Populate level 1 options
		const firstField = levels[0].target_field;
		const root = await call("geo_extension.geo_extension.locations.get_level_options", {
			country: frm.doc.country,
			level_index: 1,
		});
		set_ac_options(frm, firstField, root);
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
		/* last level */
	},
});

// -------- helpers --------

async function next_level(frm, changed_field) {
	const levels = frm._geo.levels || [];
	const idx = levels.findIndex((l) => l.target_field === changed_field);
	if (idx === -1) return;

	// Clear downstream values/options
	for (let i = idx + 1; i < levels.length; i++) {
		const f = levels[i].target_field;
		if (!frm.fields_dict[f]) continue;
		frm.set_value(f, "");
		set_ac_options(frm, f, []);
	}

	const nxt = levels[idx + 1];
	if (!nxt) return;

	// Find the code for the chosen label from our per-field map
	const label = frm.doc[changed_field] || "";
	const parent_code = lookup_code(frm, changed_field, label);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2, // API is 1-based
		parent_code,
	});
	set_ac_options(frm, nxt.target_field, rows);
}

/** Show all fields and clear suggestions (free typing still allowed). */
async function set_mode_freeform(frm) {
	frm._geo = { ...(frm._geo || {}), mode: "freeform", map: {} };
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		frm.toggle_display(f, true);
		set_ac_options(frm, f, []); // Autocomplete empty list
	}
}

/** Hard clear: values + suggestions + map (used on country change). */
function clear_levels(frm) {
	// wipe map so old label->code doesn’t leak across countries
	if (frm._geo) frm._geo.map = {};
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		// clear value
		frm.set_value(f, "");
		// clear suggestions
		set_ac_options(frm, f, []);
	}
}

/**
 * Feed Autocomplete with LABELS ONLY and cache label->code per field.
 * rows: [{label, value}] from the server.
 */
function set_ac_options(frm, fieldname, rows) {
	const ctrl = frm.fields_dict[fieldname];
	if (!ctrl) return;

	const list = (rows || []).map((r) => r.label); // labels only
	const map = Object.create(null);
	for (const r of rows || []) map[r.label] = r.value;

	if (!frm._geo) frm._geo = {};
	if (!frm._geo.map) frm._geo.map = {};
	frm._geo.map[fieldname] = map;

	if (typeof ctrl.set_data === "function") {
		ctrl.set_data(list);
	} else if (ctrl.$input && ctrl.$input[0] && ctrl.$input[0].awesomplete) {
		ctrl.$input[0].awesomplete.list = list;
	} else {
		ctrl.df.options = list;
		frm.set_df_property(fieldname, "options", list);
	}

	frm.refresh_field(fieldname);
}

/** Map label -> code for the given fieldname; fallback to raw label if unknown. */
function lookup_code(frm, fieldname, label) {
	const map = frm._geo?.map?.[fieldname] || {};
	return map[label] || (label || "").trim();
}

function call(method, args) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (r) => resolve(r.message || []),
			error: (e) => reject(e),
		});
	});
}
