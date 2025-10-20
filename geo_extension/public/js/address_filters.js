// public/js/address_filters.js

const LEVEL_FIELDS = ["state", "county", "city", "barangay"];

/**
 * Production behavior:
 * - If a manifest exists for the selected country, we:
 *   * Show only the target fields listed there
 *   * Reorder those target fields (top→bottom) immediately AFTER address_line2
 *   * Feed Autocomplete with LABELS ONLY (e.g., "Quezon City"), but keep a label->code map
 *     so cascading uses the correct parent_code.
 * - If no manifest exists, we keep the default form ordering and leave all fields visible.
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
		// Default: show everything and clear stale options; no reordering yet
		await set_mode_freeform(frm);
		if (!frm.doc.country) return;

		// Load manifest; if none → keep default ordering and freeform typing
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
			if (used.has(f)) set_ac_options(frm, f, []); // clear
		}

		// Reorder the used fields to appear after address_line2, in manifest order
		reorder_fields_by_manifest(frm, levels);

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

	// Convert the selected label to its code using our per-field map
	const label = frm.doc[changed_field] || "";
	const parent_code = lookup_code(frm, changed_field, label);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2, // 1-based
		parent_code,
	});
	set_ac_options(frm, nxt.target_field, rows);
}

async function set_mode_freeform(frm) {
	frm._geo = { mode: "freeform", levels: [], _init: true, map: {} };
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		frm.toggle_display(f, true);
		set_ac_options(frm, f, []);
	}
}

/**
 * Reorder the target fields according to manifest order,
 * placing them immediately AFTER the 'address_line2' field.
 * This is a UI-only change (DOM move), does not affect schema.
 */
function reorder_fields_by_manifest(frm, levels) {
	const order = levels
		.map((l) => l.target_field)
		.filter(
			(f) =>
				frm.fields_dict[f] &&
				frm.fields_dict[f].$wrapper &&
				frm.fields_dict["address_line2"]
		);

	if (!order.length || !frm.fields_dict["address_line2"]) return;

	const anchor = frm.fields_dict["address_line2"].$wrapper;
	let last = anchor;
	for (const f of order) {
		const wrap = frm.fields_dict[f].$wrapper;
		try {
			wrap.insertAfter(last);
			last = wrap;
		} catch (_) {
			// if insertAfter fails in a particular layout, skip gracefully
		}
	}
}

/**
 * Feed Autocomplete with LABELS ONLY and cache label->code per field.
 * rows: [{label, value}] from the server.
 */
function set_ac_options(frm, fieldname, rows) {
	const ctrl = frm.fields_dict[fieldname];
	if (!ctrl) return;

	const list = (rows || []).map((r) => r.label); // labels only in UI
	const map = Object.create(null);
	for (const r of rows || []) map[r.label] = r.value;

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

/** Find code from label for a given field; fallback to raw when not found. */
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
