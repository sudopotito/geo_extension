// public/js/address_filters.js

const LEVEL_FIELDS = ["state", "county", "city", "barangay"];

frappe.ui.form.on("Address", {
	async onload_post_render(frm) {
		// Initialize once widgets exist (so default Country is present)
		frm._geo = { mode: "freeform", levels: [], _init: false };
		await frm.trigger("country");
	},

	async refresh(frm) {
		// Apply once when the form is reopened and country already has a value
		if (!frm._geo?._init && frm.doc.country) {
			frm._geo._init = true;
			await frm.trigger("country");
		}
	},

	async country(frm) {
		// Start in freeform: show everything and clear stale suggestions
		await set_mode_freeform(frm);
		if (!frm.doc.country) return;

		// Load manifest; if none → freeform (users can type)
		let levels = [];
		try {
			levels = await call("geo_extension.geo_extension.locations.get_levels", {
				country: frm.doc.country,
			});
		} catch {
			return;
		}
		if (!levels || !levels.length) return;

		frm._geo = { mode: "guided", levels, _init: true };

		// Show fields defined by manifest; hide the rest
		const used = new Set(levels.map((l) => l.target_field));
		for (const f of LEVEL_FIELDS) {
			const ctrl = frm.fields_dict[f];
			if (!ctrl) continue;
			frm.toggle_display(f, used.has(f));
			if (used.has(f)) {
				// Autocomplete expects array options; start empty
				frm.set_df_property(f, "options", []);
				frm.refresh_field(f);
			}
		}

		// Populate level 1 (index 1 in API, first level in manifest)
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
		/* last level, nothing further to load */
	},
});

// ---- helpers ----

async function next_level(frm, changed_field) {
	const levels = frm._geo.levels || [];
	const idx = levels.findIndex((l) => l.target_field === changed_field);
	if (idx === -1) return;

	// Clear downstream values/options
	for (let i = idx + 1; i < levels.length; i++) {
		const f = levels[i].target_field;
		if (!frm.fields_dict[f]) continue;
		frm.set_value(f, "");
		frm.set_df_property(f, "options", []); // Autocomplete → array
		frm.refresh_field(f);
	}

	const nxt = levels[idx + 1];
	if (!nxt) return;

	const parent_code = extract_code(frm.doc[changed_field]);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2, // API is 1-based; next level = idx+2
		parent_code,
	});
	set_ac_options(frm, nxt.target_field, rows);
}

async function set_mode_freeform(frm) {
	// All fields visible with empty suggestions; Autocomplete still allows free typing
	frm._geo = { mode: "freeform", levels: [], _init: true };
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		frm.toggle_display(f, true);
		frm.set_df_property(f, "options", []); // clear any leftover suggestions
		frm.refresh_field(f);
	}
}

function set_ac_options(frm, fieldname, rows) {
	// Display "Name (CODE)" while storing that full string; extract_code() can parse CODE later
	const opts = (rows || []).map((r) => `${r.label} (${r.value})`);
	frm.set_df_property(fieldname, "options", opts);
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
			error: reject,
		});
	});
}
