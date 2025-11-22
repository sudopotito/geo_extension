// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

const LEVEL_FIELDS = ["state", "county", "city"];

/**
 * Behavior:
 * - Guided mode (manifest exists):
 *   * Show only fields listed in manifest, in that order
 *   * Autocomplete shows labels only
 *   * Cascading uses label→code mapping
 * - Freeform mode (no manifest or no country):
 *   * Show all LEVEL_FIELDS
 *   * No suggestions (free typing)
 *
 * Lifecycle:
 * - onload_post_render / refresh:
 *   * Rebuild autocomplete for existing doc without clearing values
 * - country handler:
 *   * React only to actual user changes to country
 */

frappe.ui.form.on("Address", {
	async onload_post_render(frm) {
		frm._geo = frm._geo || { mode: "freeform", levels: [], map: {} };
		await setup_geo_for_existing_doc(frm);
	},

	async refresh(frm) {
		frm._geo = frm._geo || { mode: "freeform", levels: [], map: {} };
		await setup_geo_for_existing_doc(frm);
	},

	// Only treat this as a *user* change of country.
	// We do NOT call this from our init logic.
	async country(frm) {
		// User cleared country → go full freeform
		if (!frm.doc.country) {
			clear_levels(frm, { clear_values: true });
			await set_mode_freeform(frm);
			frm._geo.mode = "freeform";
			frm._geo.levels = [];
			return;
		}

		// New country selected → nuke existing hierarchy (values + options)
		clear_levels(frm, { clear_values: true });

		let levels = [];
		try {
			levels =
				(await call("geo_extension.geo_extension.locations.get_levels", {
					country: frm.doc.country,
				})) || [];
		} catch {
			await set_mode_freeform(frm);
			frm._geo.mode = "freeform";
			frm._geo.levels = [];
			return;
		}

		if (!levels.length) {
			await set_mode_freeform(frm);
			frm._geo.mode = "freeform";
			frm._geo.levels = [];
			return;
		}

		// Enter guided mode
		frm._geo.mode = "guided";
		frm._geo.levels = levels;
		frm._geo.map = {};

		// Show only manifest fields
		const used = new Set(levels.map((l) => l.target_field));
		for (const f of LEVEL_FIELDS) {
			if (!frm.fields_dict[f]) continue;
			frm.toggle_display(f, used.has(f));
			if (used.has(f)) set_ac_options(frm, f, []);
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
		if (frm._geo?.mode === "guided") await next_level(frm, "state");
	},
	async county(frm) {
		if (frm._geo?.mode === "guided") await next_level(frm, "county");
	},
	async city(frm) {
		if (frm._geo?.mode === "guided") await next_level(frm, "city");
	},
});

// -------- init helpers (load / refresh) --------

/**
 * Runs on load + refresh.
 * Goal: rebuild autocomplete + visibility WITHOUT clearing stored values.
 */
async function setup_geo_for_existing_doc(frm) {
	const country = frm.doc.country;

	// No country selected → just freeform everything.
	if (!country) {
		await set_mode_freeform(frm);
		frm._geo.mode = "freeform";
		frm._geo.levels = [];
		return;
	}

	let levels = [];
	try {
		levels =
			(await call("geo_extension.geo_extension.locations.get_levels", {
				country,
			})) || [];
	} catch {
		levels = [];
	}

	// No manifest → freeform
	if (!levels.length) {
		await set_mode_freeform(frm);
		frm._geo.mode = "freeform";
		frm._geo.levels = [];
		return;
	}

	// Guided mode for this doc
	frm._geo.mode = "guided";
	frm._geo.levels = levels;
	frm._geo.map = {};

	// Show only manifest fields
	const used = new Set(levels.map((l) => l.target_field));
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		frm.toggle_display(f, used.has(f));
		if (used.has(f)) {
			// We'll set real options below per level
			set_ac_options(frm, f, []);
		}
	}

	// Rebuild suggestions chain based on existing values.
	// This avoids clearing values and avoids visual "jumping".
	let parent_code = null;

	for (let i = 0; i < levels.length; i++) {
		const lvl = levels[i];
		const fieldname = lvl.target_field;

		// if there's no field (customization mismatch), skip
		if (!frm.fields_dict[fieldname]) continue;

		const args = {
			country,
			level_index: i + 1, // API is 1-based
		};

		if (i > 0) {
			// for levels beyond 1, we can only fetch filtered options
			// if we know the parent_code; otherwise stop here.
			if (!parent_code) {
				set_ac_options(frm, fieldname, []);
				break;
			}
			args.parent_code = parent_code;
		}

		const rows = await call("geo_extension.geo_extension.locations.get_level_options", args);
		set_ac_options(frm, fieldname, rows);

		// Try to align parent_code with current saved value
		const current_label = frm.doc[fieldname];
		if (current_label) {
			const match = (rows || []).find((r) => r.label === current_label);
			parent_code = match ? match.value : null;
		} else {
			parent_code = null;
		}
	}
}

// -------- cascading helpers --------

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

// -------- mode + utility helpers --------

/** Show all fields and clear suggestions (free typing still allowed). */
async function set_mode_freeform(frm) {
	frm._geo = { ...(frm._geo || {}), mode: "freeform", map: {} };
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		frm.toggle_display(f, true);
		set_ac_options(frm, f, []); // empty autocomplete
	}
}

/**
 * Clear suggestions for all levels.
 * If clear_values = true → also clear doc fields.
 */
function clear_levels(frm, { clear_values = true } = {}) {
	if (frm._geo) frm._geo.map = {};
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		if (clear_values) {
			frm.set_value(f, "");
		}
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

	const list = (rows || []).map((r) => r.label);
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
