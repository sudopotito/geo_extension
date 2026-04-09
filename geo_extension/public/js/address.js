// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

const LEVEL_FIELDS = ["state", "city", "county"];

// Default order for unsupported countries (matches native Address doctype)
const DEFAULT_LEVEL_ORDER = ["city", "county", "state"];

/**
 * Geo Extension - Address Enhancement
 *
 * Behavior:
 * - Country field always appears immediately after address_type (via install.py)
 * - When country is selected with manifest support:
 *   * Fields are REARRANGED per country's administrative hierarchy
 *   * Autocomplete suggestions provided for guided fields
 *   * ALL fields remain visible - nothing is hidden
 * - When country has no manifest support:
 *   * Default field order maintained (city -> county -> state)
 *   * No autocomplete suggestions (free typing)
 */

frappe.ui.form.on("Address", {
	async onload_post_render(frm) {
		frm._geo = frm._geo || { mode: "freeform", levels: [], map: {} };
		await setup_geo_for_existing_doc(frm);
	},

	async refresh(frm) {
		frm._geo = frm._geo || { mode: "freeform", levels: [], map: {} };
		// Only setup autocomplete, don't rearrange on refresh (causes loops)
		if (frm._geo.mode === "guided" && frm._geo.levels.length) {
			update_field_labels(frm, frm._geo.levels);
		}
	},

	async country(frm) {
		// Clear existing hierarchy values when country changes
		clear_level_values(frm);
		clear_autocomplete_options(frm);

		if (!frm.doc.country) {
			// Reset to freeform mode and default arrangement
			frm._geo.mode = "freeform";
			frm._geo.levels = [];
			frm._geo.map = {};
			reset_field_labels(frm);
			arrange_level_fields(frm, DEFAULT_LEVEL_ORDER);
			return;
		}

		let levels = [];
		try {
			levels =
				(await call("geo_extension.geo_extension.locations.get_levels", {
					country: frm.doc.country,
				})) || [];
		} catch {
			levels = [];
		}

		if (!levels.length) {
			// No manifest for this country - freeform mode with default arrangement
			frm._geo.mode = "freeform";
			frm._geo.levels = [];
			frm._geo.map = {};
			reset_field_labels(frm);
			arrange_level_fields(frm, DEFAULT_LEVEL_ORDER);
			return;
		}

		// Enter guided mode
		frm._geo.mode = "guided";
		frm._geo.levels = levels;
		frm._geo.map = {};

		// Get the desired field order from manifest
		const levelFieldOrder = levels
			.map((l) => l.target_field)
			.filter((f) => LEVEL_FIELDS.includes(f));

		// Add any missing fields at the end
		for (const f of LEVEL_FIELDS) {
			if (!levelFieldOrder.includes(f)) levelFieldOrder.push(f);
		}

		// Arrange fields
		arrange_level_fields(frm, levelFieldOrder);
		update_field_labels(frm, levels);

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
	async city(frm) {
		if (frm._geo?.mode === "guided") await next_level(frm, "city");
	},
	async county(frm) {
		if (frm._geo?.mode === "guided") await next_level(frm, "county");
	},
});

/**
 * Arrange level fields using CSS flexbox order property.
 * This is much more reliable than DOM manipulation.
 */
function arrange_level_fields(frm, desiredOrder) {
	// Get the wrapper that contains all level fields
	// In Frappe, fields are typically in .row or .form-section
	const levelWrappers = {};
	let container = null;

	for (const fieldname of LEVEL_FIELDS) {
		const field = frm.fields_dict[fieldname];
		if (field && field.$wrapper) {
			levelWrappers[fieldname] = field.$wrapper;
			if (!container) {
				container = field.$wrapper.parent();
			}
		}
	}

	if (!container || !container.length) return;

	// Apply flexbox ordering
	// We use CSS order property: lower values appear first
	container.css("display", "flex");
	container.css("flex-direction", "column");

	desiredOrder.forEach((fieldname, index) => {
		const $wrapper = levelWrappers[fieldname];
		if ($wrapper && $wrapper.length) {
			$wrapper.css("order", index);
		}
	});
}

/**
 * Update field labels to show country-specific terms.
 */
function update_field_labels(frm, levels) {
	// Reset all to defaults first
	reset_field_labels(frm);

	// Then update based on manifest
	for (const level of levels) {
		const field = frm.fields_dict[level.target_field];
		if (field && field.df) {
			// Store original label if not stored
			if (!frm._geo.original_labels) {
				frm._geo.original_labels = {};
			}
			if (!frm._geo.original_labels[level.target_field]) {
				frm._geo.original_labels[level.target_field] = field.df.label;
			}

			// Update label to show country-specific term
			field.df.label = level.label;
			frm.refresh_field(level.target_field);
		}
	}
}

/**
 * Reset field labels to their default values.
 */
function reset_field_labels(frm) {
	const defaultLabels = {
		state: "State/Province",
		city: "City/Town",
		county: "County",
	};

	for (const [fieldname, defaultLabel] of Object.entries(defaultLabels)) {
		const field = frm.fields_dict[fieldname];
		if (field && field.df) {
			// Restore original if we have it, otherwise use default
			if (frm._geo?.original_labels?.[fieldname]) {
				field.df.label = frm._geo.original_labels[fieldname];
			} else {
				field.df.label = defaultLabel;
			}
			frm.refresh_field(fieldname);
		}
	}
}

async function setup_geo_for_existing_doc(frm) {
	const country = frm.doc.country;

	if (!country) {
		frm._geo.mode = "freeform";
		frm._geo.levels = [];
		frm._geo.map = {};
		reset_field_labels(frm);
		clear_autocomplete_options(frm);
		arrange_level_fields(frm, DEFAULT_LEVEL_ORDER);
		return;
	}

	let levels = [];
	try {
		levels =
			(await call("geo_extension.geo_extension.locations.get_levels", { country })) || [];
	} catch {
		levels = [];
	}

	if (!levels.length) {
		frm._geo.mode = "freeform";
		frm._geo.levels = [];
		frm._geo.map = {};
		reset_field_labels(frm);
		clear_autocomplete_options(frm);
		arrange_level_fields(frm, DEFAULT_LEVEL_ORDER);
		return;
	}

	frm._geo.mode = "guided";
	frm._geo.levels = levels;
	frm._geo.map = {};

	// Get field order from manifest
	const levelFieldOrder = levels
		.map((l) => l.target_field)
		.filter((f) => LEVEL_FIELDS.includes(f));
	for (const f of LEVEL_FIELDS) {
		if (!levelFieldOrder.includes(f)) levelFieldOrder.push(f);
	}

	arrange_level_fields(frm, levelFieldOrder);
	update_field_labels(frm, levels);
	clear_autocomplete_options(frm);

	// Rebuild suggestions chain based on existing values
	let parent_code = null;

	for (let i = 0; i < levels.length; i++) {
		const lvl = levels[i];
		const fieldname = lvl.target_field;

		if (!frm.fields_dict[fieldname]) continue;

		const args = { country, level_index: i + 1 };

		if (i > 0) {
			if (!parent_code) {
				set_ac_options(frm, fieldname, []);
				continue;
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

async function next_level(frm, changed_field) {
	const levels = frm._geo.levels || [];
	const idx = levels.findIndex((l) => l.target_field === changed_field);
	if (idx === -1) return;

	// Clear downstream values/options only (not hiding fields)
	for (let i = idx + 1; i < levels.length; i++) {
		const f = levels[i].target_field;
		if (!frm.fields_dict[f]) continue;
		frm.set_value(f, "");
		set_ac_options(frm, f, []);
	}

	const nxt = levels[idx + 1];
	if (!nxt) return;

	const label = frm.doc[changed_field] || "";
	const parent_code = lookup_code(frm, changed_field, label);
	if (!parent_code) return;

	const rows = await call("geo_extension.geo_extension.locations.get_level_options", {
		country: frm.doc.country,
		level_index: idx + 2,
		parent_code,
	});
	set_ac_options(frm, nxt.target_field, rows);
}

/**
 * Clear values for level fields when country changes.
 */
function clear_level_values(frm) {
	if (frm._geo) frm._geo.map = {};
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		frm.set_value(f, "");
	}
}

/**
 * Clear autocomplete options but keep fields visible.
 */
function clear_autocomplete_options(frm) {
	if (frm._geo) frm._geo.map = {};
	for (const f of LEVEL_FIELDS) {
		if (!frm.fields_dict[f]) continue;
		set_ac_options(frm, f, []);
	}
}

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
