// Copyright (c) 2025, sudo potito and contributors
// For license information, please see license.txt

/**
 * Geo Extension - reusable cascading geographic selector.
 *
 * Exposes `frappe.geo_extension`:
 *
 *   client.get_hierarchy(country)                -> {supported, levels:[{level,label,target_field}], postal_codes}
 *   client.get_options(country, level, parent)   -> [{value, label}]
 *   client.get_postal_codes(country, level, code)-> {codes:[...], level}
 *   client.resolve(country, names)               -> [{level, value, label}]
 *   client.clear_cache()
 *
 *   GeoCascade   country-agnostic cascade engine working through an adapter
 *   FormAdapter  adapter for desk forms (frappe.ui.form.Form)
 *   FieldGroupAdapter adapter for dialogs and website Web Forms (any frappe.ui.FieldGroup)
 *   attach_to_field_group(group) wires a dialog/Web Form with address fields automatically
 *   attach_suggestions(input, provider) / detach_suggestions(input)
 *
 * The engine never restricts input: suggestions are attached to plain Data
 * inputs, values that do not match the dataset are kept as typed, and only a
 * deliberate selection (or clearing) of a level cascades to lower levels.
 *
 * Load in another app/page with: frappe.require("/assets/geo_extension/js/geo_selector.js")
 *
 * This file is also inlined into Address Web Forms (hooks.webform_include_js),
 * where Frappe renders it as a Jinja template: it must never contain Jinja
 * delimiters (double braces, brace-percent, brace-hash) or a dot followed by
 * two underscores (see tests/js/test_field_group.js).
 */

(function () {
	if (window.frappe && frappe.geo_extension && frappe.geo_extension.GeoCascade) return;
	frappe.provide("frappe.geo_extension");

	const METHODS = {
		hierarchy: "geo_extension.api.get_hierarchy",
		options: "geo_extension.api.get_options",
		resolve: "geo_extension.api.resolve",
		postal: "geo_extension.api.get_postal_codes",
	};

	// ------------------------------------------------------------------
	// API client with browser-side cache
	// ------------------------------------------------------------------

	const cache = new Map();

	function call(method, args) {
		return new Promise((resolve, reject) => {
			frappe.call({
				method,
				args,
				callback: (r) => resolve(r ? r.message : null),
				error: (e) => reject(e),
			});
		});
	}

	function cached(key, fetcher) {
		if (!cache.has(key)) {
			const p = fetcher().catch((e) => {
				cache.delete(key);
				throw e;
			});
			cache.set(key, p);
		}
		return cache.get(key);
	}

	const client = {
		get_hierarchy(country) {
			if (!country) return Promise.resolve({ supported: false, levels: [] });
			return cached(`h:${country}`, () =>
				call(METHODS.hierarchy, { country }).then(
					(r) => r || { supported: false, levels: [] }
				)
			);
		},
		get_options(country, level, parent, txt) {
			if (!country || (level > 1 && !parent)) return Promise.resolve([]);
			const key = `o:${country}:${level}:${parent || ""}:${txt || ""}`;
			return cached(key, () =>
				call(METHODS.options, {
					country,
					level,
					parent: parent || null,
					txt: txt || null,
				}).then((r) => r || [])
			);
		},
		get_postal_codes(country, level, code) {
			if (!country || !code) return Promise.resolve({ codes: [], level: null });
			return cached(`p:${country}:${level}:${code}`, () =>
				call(METHODS.postal, { country, level, code }).then(
					(r) => r || { codes: [], level: null }
				)
			);
		},
		resolve(country, names) {
			if (!country || !(names || []).some(Boolean)) return Promise.resolve([]);
			return call(METHODS.resolve, { country, names: JSON.stringify(names) }).then(
				(r) => r || []
			);
		},
		clear_cache() {
			cache.clear();
		},
	};

	// ------------------------------------------------------------------
	// suggestion dropdown on plain inputs (Awesomplete ships with Frappe)
	// ------------------------------------------------------------------

	function normalize(text) {
		return (text || "")
			.normalize("NFKD")
			.replace(/[̀-ͯ]/g, "")
			.replace(/\s+/g, " ")
			.trim()
			.toLowerCase()
			.replace(/ı/g, "i"); // Turkish dotless i has no decomposition
	}

	function find_option(options, label) {
		const key = normalize(label);
		if (!key) return null;
		const list = options || [];
		return (
			list.find((o) => normalize(o.label) === key) ||
			list.find((o) => (o.aliases || []).some((a) => normalize(a) === key)) ||
			null
		);
	}

	async function refresh_list(input) {
		const aw = input._geo_awesomplete;
		const provider = input._geo_provider;
		if (!aw || !provider) return;
		let items = [];
		try {
			items = (await provider()) || [];
		} catch (e) {
			items = [];
		}
		if (input._geo_provider !== provider) return; // superseded meanwhile
		if (items.length) {
			// aliases are not part of Awesomplete's suggestion text; keep them for the filter
			const alias_map = Object.create(null);
			for (const item of items)
				if (item.aliases && item.aliases.length) alias_map[item.value] = item.aliases;
			input._geo_aliases = alias_map;
			aw.list = items; // the setter re-evaluates while the input is focused
		} else {
			aw.list = [];
			aw.close();
		}
	}

	/**
	 * Attach (or re-point) a suggestion dropdown to an <input>.
	 * `provider` is an async function returning [{value, label}].
	 */
	function attach_suggestions(input, provider) {
		if (!input || typeof window.Awesomplete !== "function") return null;
		let aw = input._geo_awesomplete;
		if (!aw) {
			aw = new window.Awesomplete(input, {
				minChars: 0,
				maxItems: 50,
				autoFirst: false,
				sort: false,
				filter(suggestion, text) {
					if (window.Awesomplete.FILTER_CONTAINS(suggestion.label, text)) return true;
					const aliases = (input._geo_aliases || {})[suggestion.value] || [];
					return aliases.some((alias) =>
						window.Awesomplete.FILTER_CONTAINS(alias, text)
					);
				},
				replace(suggestion) {
					this.input.value = suggestion.label;
				},
			});
			input._geo_awesomplete = aw;
			$(input).on("focus.geo_extension", () => {
				if (!input.value) refresh_list(input);
			});
			$(input).on("input.geo_extension", () => {
				if (!aw._list || !aw._list.length) refresh_list(input);
			});
			$(input).on("awesomplete-selectcomplete.geo_extension", () => {
				$(input).trigger("change");
			});
		}
		input._geo_provider = provider;
		return aw;
	}

	function detach_suggestions(input) {
		if (!input || !input._geo_awesomplete) return;
		input._geo_provider = null;
		input._geo_awesomplete.list = [];
		input._geo_awesomplete.close();
	}

	// ------------------------------------------------------------------
	// adapters
	// ------------------------------------------------------------------

	const original_labels = new Map();

	class FormAdapter {
		constructor(frm) {
			this.frm = frm;
		}
		has_field(fieldname) {
			return !!this.frm.fields_dict[fieldname];
		}
		get_value(fieldname) {
			return this.frm.doc[fieldname];
		}
		set_value(fieldname, value) {
			return this.frm.set_value(fieldname, value);
		}
		get_input(fieldname) {
			const ctrl = this.frm.fields_dict[fieldname];
			return ctrl && ctrl.$input ? ctrl.$input.get(0) : null;
		}
		set_label(fieldname, label) {
			const df = frappe.meta.get_docfield(this.frm.doctype, fieldname);
			if (!df) return;
			const key = `${this.frm.doctype}:${fieldname}`;
			if (!original_labels.has(key)) original_labels.set(key, df.label);
			this.frm.set_df_property(fieldname, "label", label);
		}
		restore_label(fieldname) {
			const key = `${this.frm.doctype}:${fieldname}`;
			if (original_labels.has(key)) {
				this.frm.set_df_property(fieldname, "label", original_labels.get(key));
			}
		}
		attach_suggestions(fieldname, provider) {
			attach_suggestions(this.get_input(fieldname), provider);
		}
		detach_suggestions(fieldname) {
			detach_suggestions(this.get_input(fieldname));
		}
	}

	/**
	 * Adapter for any frappe.ui.FieldGroup: dialogs (quick entry) and website
	 * Web Forms (frappe.web_form). Both expose fields_dict/get_value/set_value.
	 */
	class FieldGroupAdapter {
		constructor(group) {
			this.group = group;
			this.original_labels = {};
		}
		field(fieldname) {
			return this.group.fields_dict && this.group.fields_dict[fieldname];
		}
		has_field(fieldname) {
			return !!this.field(fieldname);
		}
		get_value(fieldname) {
			return this.group.get_value(fieldname);
		}
		set_value(fieldname, value) {
			return Promise.resolve(this.group.set_value(fieldname, value));
		}
		get_input(fieldname) {
			const ctrl = this.field(fieldname);
			return ctrl && ctrl.$input ? ctrl.$input.get(0) : null;
		}
		set_label(fieldname, label) {
			const ctrl = this.field(fieldname);
			if (!ctrl || typeof ctrl.set_label !== "function") return;
			if (!(fieldname in this.original_labels))
				this.original_labels[fieldname] = ctrl.df.label;
			ctrl.set_label(label);
		}
		restore_label(fieldname) {
			const ctrl = this.field(fieldname);
			if (ctrl && fieldname in this.original_labels)
				ctrl.set_label(this.original_labels[fieldname]);
		}
		attach_suggestions(fieldname, provider) {
			attach_suggestions(this.get_input(fieldname), provider);
		}
		detach_suggestions(fieldname) {
			detach_suggestions(this.get_input(fieldname));
		}
	}

	// ERPNext's contact/address quick entry names the country field "country_address"
	const COUNTRY_FIELDS = ["country", "country_address"];
	const LEVEL_FIELDS = ["state", "county", "city", "address_line2"];

	/** Run `handler` after the field's existing df.change (FieldGroup controls call df.change). */
	function on_field_change(group, fieldname, handler) {
		const ctrl = group.fields_dict[fieldname];
		if (!ctrl) return;
		const df = ctrl.df;
		const previous = df.change || df.onchange;
		df.change = function () {
			const result = previous ? previous.apply(this, arguments) : undefined;
			handler();
			return result;
		};
	}

	/**
	 * Attach the cascade to a dialog or Web Form that has a country field and at
	 * least one address level field. Returns the state object ({cascade}) or null
	 * when the group has no address fields. Safe to call more than once.
	 */
	function attach_to_field_group(group, { country_fields = COUNTRY_FIELDS } = {}) {
		if (!group || !group.fields_dict) return null;
		if (group._geo_cascade) return group._geo_cascade;
		const country_field = country_fields.find((f) => group.fields_dict[f]);
		if (!country_field) return null;
		if (!LEVEL_FIELDS.some((f) => group.fields_dict[f])) return null;

		const adapter = new FieldGroupAdapter(group);
		const state = { cascade: null, adapter };
		group._geo_cascade = state;

		const setup = async () => {
			if (state.cascade) state.cascade.teardown();
			const cascade = new GeoCascade({ country: group.get_value(country_field), adapter });
			state.cascade = cascade;
			if (group.get_value(country_field)) await cascade.setup();
			return cascade;
		};

		on_field_change(group, country_field, async () => {
			const old = state.cascade;
			if (old) {
				const fields = new Set(LEVEL_FIELDS.filter((f) => f !== "address_line2"));
				old.level_fields.forEach((f) => fields.add(f));
				const auto = old.auto_postal;
				old.teardown();
				state.cascade = null;
				if (auto && group.get_value("pincode") === auto)
					await adapter.set_value("pincode", "");
				for (const f of fields) {
					if (group.fields_dict[f] && group.get_value(f)) await adapter.set_value(f, "");
				}
			}
			state.ready = setup();
		});
		for (const f of LEVEL_FIELDS) {
			if (!group.fields_dict[f]) continue;
			on_field_change(group, f, () => {
				if (state.cascade && state.cascade.handles(f)) state.cascade.handle_change(f);
			});
		}
		state.ready = setup();
		return state;
	}

	// ------------------------------------------------------------------
	// cascade engine
	// ------------------------------------------------------------------

	class GeoCascade {
		/**
		 * @param {Object} opts
		 * @param {string} opts.country       Country name or ISO code
		 * @param {Object} opts.adapter       FormAdapter / WebFormAdapter / custom
		 * @param {string} [opts.postal_field="pincode"]
		 */
		constructor({ country, adapter, postal_field = "pincode" }) {
			this._chain = Promise.resolve();
			this.country = country;
			this.adapter = adapter;
			this.postal_field = postal_field;
			this.supported = false;
			this.levels = [];
			this.codes = [];
			this.postal = { available: false };
			this.postal_options = [];
			this.auto_postal = null;
			this._suspended = 0;
			this._generation = 0;
		}

		get level_fields() {
			return this.levels.map((l) => l.target_field);
		}

		/** Load the hierarchy, decorate the fields and resolve already-entered values. */
		async setup() {
			const generation = ++this._generation;
			let hierarchy = null;
			try {
				hierarchy = await client.get_hierarchy(this.country);
			} catch (e) {
				hierarchy = null;
			}
			if (generation !== this._generation) return this;
			if (!hierarchy || !hierarchy.supported) {
				this.supported = false;
				this.levels = [];
				return this;
			}

			this.supported = true;
			this.levels = (hierarchy.levels || []).filter((l) =>
				this.adapter.has_field(l.target_field)
			);
			this.postal = hierarchy.postal_codes || { available: false };
			this.codes = this.levels.map(() => null);

			this.levels.forEach((lvl, i) => {
				this.adapter.set_label(lvl.target_field, __(lvl.label));
				this.adapter.attach_suggestions(lvl.target_field, () => this.options_for(i));
			});
			if (this.postal.available && this.adapter.has_field(this.postal_field)) {
				this.adapter.attach_suggestions(
					this.postal_field,
					async () => this.postal_options
				);
			}

			await this.resolve_existing();
			return this;
		}

		/** Map values already in the fields to stable codes (no values are changed). */
		async resolve_existing() {
			const names = this.levels.map((l) =>
				(this.adapter.get_value(l.target_field) || "").trim()
			);
			this.codes = this.levels.map(() => null);
			if (!names.some(Boolean)) return;
			let chain = [];
			try {
				chain = (await client.resolve(this.country, names)) || [];
			} catch (e) {
				chain = [];
			}
			chain.forEach((unit, i) => {
				if (this.levels[i] && unit.level === this.levels[i].level)
					this.codes[i] = unit.value;
			});
			await this.refresh_postal({ apply: false });
		}

		field_index(fieldname) {
			return this.levels.findIndex((l) => l.target_field === fieldname);
		}

		handles(fieldname) {
			return this.supported && this.field_index(fieldname) !== -1;
		}

		/** Options for level i (0-based), filtered by the selected parent. */
		options_for(i) {
			const lvl = this.levels[i];
			if (!lvl) return Promise.resolve([]);
			const parent = i > 0 ? this.codes[i - 1] : null;
			if (i > 0 && !parent) return Promise.resolve([]);
			return client.get_options(this.country, lvl.level, parent);
		}

		/**
		 * Call when the user changed a level field.
		 * - a value matching the dataset becomes the selected unit
		 * - a different selection (or clearing the field) clears the lower levels
		 * - free text that matches nothing is kept as typed; lower levels are left alone
		 */
		/**
		 * React to a value change in one of the level fields. Calls are serialised
		 * so a change in a lower level always sees the resolved code of the level
		 * above it, even when the user types faster than the options load.
		 */
		handle_change(fieldname) {
			const run = this._chain.then(() => this._handle_change(fieldname));
			this._chain = run.catch(() => {});
			return run;
		}

		async _handle_change(fieldname) {
			if (!this.supported || this._suspended) return;
			const i = this.field_index(fieldname);
			if (i === -1) return;

			const value = (this.adapter.get_value(fieldname) || "").trim();
			const previous = this.codes[i];
			let code = null;
			if (value) {
				let options = [];
				try {
					options = await this.options_for(i);
				} catch (e) {
					options = [];
				}
				const match = find_option(options, value);
				code = match ? match.value : null;
			}
			// the user may have kept typing while we were fetching
			if ((this.adapter.get_value(fieldname) || "").trim() !== value) return;

			this.codes[i] = code;
			const deliberate = !value || (code && code !== previous);
			if (deliberate) {
				await this.clear_below(i);
			} else if (code !== previous) {
				// parent is now free text: lower values stay, but they no longer identify units
				for (let j = i + 1; j < this.codes.length; j++) this.codes[j] = null;
			}
			if (code && i + 1 < this.levels.length) this.options_for(i + 1).catch(() => {});
			if (code !== previous) await this.refresh_postal({ apply: true });
		}

		async clear_below(i) {
			this._suspended++;
			try {
				for (let j = i + 1; j < this.levels.length; j++) {
					this.codes[j] = null;
					const f = this.levels[j].target_field;
					if (this.adapter.get_value(f)) await this.adapter.set_value(f, "");
				}
			} finally {
				this._suspended--;
			}
		}

		deepest_selected() {
			for (let i = this.codes.length - 1; i >= 0; i--) if (this.codes[i]) return i;
			return -1;
		}

		/**
		 * Postal code handling:
		 * - exactly one known code: fill the field unless the user typed something else
		 * - several codes: offer them as suggestions, never guess
		 * - none: leave the field alone (an earlier auto-filled value is retracted)
		 */
		async refresh_postal({ apply }) {
			if (
				!this.postal ||
				!this.postal.available ||
				!this.adapter.has_field(this.postal_field)
			)
				return;
			const i = this.deepest_selected();
			let codes = [];
			if (i >= 0) {
				try {
					const r = await client.get_postal_codes(
						this.country,
						this.levels[i].level,
						this.codes[i]
					);
					codes = (r && r.codes) || [];
				} catch (e) {
					codes = [];
				}
			}
			this.postal_options = codes.map((c) => ({ label: c, value: c }));
			if (!apply) return;

			const current = (this.adapter.get_value(this.postal_field) || "").trim();
			const is_auto = !!current && current === this.auto_postal;
			if (codes.length === 1) {
				if (!current || is_auto) {
					if (current !== codes[0]) await this.set_silently(this.postal_field, codes[0]);
					this.auto_postal = codes[0];
				}
			} else if (is_auto) {
				if (!codes.includes(current)) {
					await this.set_silently(this.postal_field, "");
					this.auto_postal = null;
				}
			}
		}

		async set_silently(fieldname, value) {
			this._suspended++;
			try {
				await this.adapter.set_value(fieldname, value);
			} finally {
				this._suspended--;
			}
		}

		/** Clear every level value (used when the country changes). Manual postal codes are kept. */
		async clear_values() {
			this._suspended++;
			try {
				for (const lvl of this.levels) {
					if (this.adapter.get_value(lvl.target_field))
						await this.adapter.set_value(lvl.target_field, "");
				}
				const current = (this.adapter.get_value(this.postal_field) || "").trim();
				if (current && current === this.auto_postal)
					await this.adapter.set_value(this.postal_field, "");
			} finally {
				this._suspended--;
			}
			this.codes = this.levels.map(() => null);
			this.auto_postal = null;
			this.postal_options = [];
		}

		/** Undo labels and suggestions; the cascade becomes inert. */
		teardown() {
			this._generation++;
			for (const lvl of this.levels) {
				this.adapter.restore_label(lvl.target_field);
				this.adapter.detach_suggestions(lvl.target_field);
			}
			if (this.adapter.has_field(this.postal_field))
				this.adapter.detach_suggestions(this.postal_field);
			this.supported = false;
			this.levels = [];
			this.codes = [];
			this.postal_options = [];
		}
	}

	Object.assign(frappe.geo_extension, {
		client,
		GeoCascade,
		FormAdapter,
		FieldGroupAdapter,
		attach_to_field_group,
		attach_suggestions,
		detach_suggestions,
		normalize,
		find_option,
	});
})();
