// public/js/address_filters.js

const LEVEL_FIELDS = ["state", "county", "city", "barangay"];

function log(...a) {
	try {
		console.log("[geo]", ...a);
	} catch (_) {}
}

frappe.ui.form.on("Address", {
	async onload_post_render(frm) {
		// Full form only; quick-entry dialogs won't bind this script
		if (!frm.wrapper || !frm.fields_dict) return;

		frm._geo = { mode: "freeform", levels: [], _init: false };
		log("onload_post_render; country =", frm.doc.country);
		await frm.trigger("country");
	},

	async refresh(frm) {
		if (!frm._geo?._init && frm.doc.country) {
			frm._geo._init = true;
			log("refresh init; country =", frm.doc.country);
			await frm.trigger("country");
		}
	},

	async country(frm) {
		log("country() start", frm.doc.country);
		// Show all fields (we'll hide unused after manifest) + clear any stale lists
		for (const f of LEVEL_FIELDS) {
			if (!frm.fields_dict[f]) continue;
			frm.toggle_display(f, true);
			set_ac_options(frm, f, []); // empty list still allows free typing
		}
		if (!frm.doc.country) return;

		let levels = [];
		try {
			levels =
				(await call("geo_extension.geo_extension.locations.get_levels", {
					country: frm.doc.country,
				})) || [];
			log("levels:", levels);
		} catch (e) {
			console.error("[geo] get_levels error", e);
			return;
		}
		if (!levels.length) {
			log("no levels -> freeform");
			return;
		}

		frm._geo = { mode: "guided", levels, _init: true };

		// Hide fields that are NOT in manifest; prepare used fields
		const used = new Set(levels.map((l) => l.target_field));
		for (const f of LEVEL_FIELDS) {
			const ctrl = frm.fields_dict[f];
			if (!ctrl) continue;
			frm.toggle_display(f, used.has(f));
			if (used.has(f)) {
				set_ac_options(frm, f, []); // start empty
			}
		}

		// Populate level 1
		const firstField = levels[0].target_field;
		const root = await call("geo_extension.geo_extension.locations.get_level_options", {
			country: frm.doc.country,
			level_index: 1,
		});
		log("level1 options for", firstField, root);
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

// ---- helpers ----

async function next_level(frm, changed_field) {
	const levels = frm._geo.levels || [];
	const idx = levels.findIndex((l) => l.target_field === changed_field);
	if (idx === -1) return;

	// Clear downstream
	for (let i = idx + 1; i < levels.length; i++) {
		const f = levels[i].target_field;
		if (!frm.fields_dict[f]) continue;
		frm.set_value(f, "");
		set_ac_options(frm, f, []);
	}

	const nxt = levels[idx + 1];
	if (!nxt) return;

	const parent_code = extract_code(frm.doc[changed_field]);
	log("next_level parent_code for", changed_field, "=", parent_code);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2, // 1-based
		parent_code,
	});
	log("options for", nxt.target_field, rows);
	set_ac_options(frm, nxt.target_field, rows);
}

function set_ac_options(frm, fieldname, rows) {
	const ctrl = frm.fields_dict[fieldname];
	if (!ctrl) return;

	// Convert rows -> "Name (CODE)" list
	const list = (rows || []).map((r) => `${r.label} (${r.value})`);

	// 1) Preferred: ControlAutocomplete API
	if (typeof ctrl.set_data === "function") {
		ctrl.set_data(list);
		log("set_data()", fieldname, list.length);
	}
	// 2) Direct Awesomplete (works on most builds)
	else if (ctrl.$input && ctrl.$input[0] && ctrl.$input[0].awesomplete) {
		ctrl.$input[0].awesomplete.list = list;
		log("awesomplete.list =", fieldname, list.length);
	}
	// 3) Fallback: df.options (some builds read this)
	else {
		ctrl.df.options = list;
		frm.set_df_property(fieldname, "options", list);
		log("df.options[]", fieldname, list.length);
	}

	// Refresh to ensure UI picks it up
	frm.refresh_field(fieldname);
}

function extract_code(val) {
	if (!val) return "";
	const m = String(val).match(/\(([^)]+)\)\s*$/);
	return m ? m[1] : String(val).trim();
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
