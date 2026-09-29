// Minimal browser/Frappe environment so geo_selector.js can be loaded under node:test.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function make_env({ responses = {} } = {}) {
	const calls = [];
	const env = {
		calls,
		responses, // method -> (args) => value
		reset() {
			calls.length = 0;
		},
	};
	const $ = (el) => ({
		on() {
			return this;
		},
		trigger(name) {
			if (el && el.__handlers && el.__handlers[name]) el.__handlers[name]();
			return this;
		},
	});
	const frappe = {
		provide(ns) {
			ns.split(".").reduce((o, k) => (o[k] = o[k] || {}), globalThis);
		},
		call({ method, args, callback, error }) {
			calls.push({ method, args });
			const fn = env.responses[method];
			setTimeout(() => {
				try {
					callback({ message: fn ? fn(args) : null });
				} catch (e) {
					error && error(e);
				}
			}, 0);
		},
		meta: { get_docfield: () => null },
	};
	Object.assign(globalThis, { window: globalThis, frappe, $, __: (s) => s });
	delete globalThis.Awesomplete; // suggestions are optional; tests use a fake adapter
	delete frappe.geo_extension;
	const src = fs.readFileSync(
		path.join(__dirname, "..", "..", "geo_extension", "public", "js", "geo_selector.js"),
		"utf8"
	);
	vm.runInThisContext(src, { filename: "geo_selector.js" });
	env.geo = frappe.geo_extension;
	return env;
}

/** In-memory adapter standing in for a form: values, labels and suggestion providers. */
class FakeAdapter {
	constructor(fields) {
		this.values = {};
		this.labels = {};
		this.providers = {};
		this.fields = fields;
		this.log = [];
	}
	has_field(f) {
		return this.fields.includes(f);
	}
	get_value(f) {
		return this.values[f];
	}
	async set_value(f, v) {
		this.values[f] = v;
		this.log.push([f, v]);
	}
	get_input() {
		return null;
	}
	set_label(f, l) {
		this.labels[f] = l;
	}
	restore_label(f) {
		delete this.labels[f];
	}
	attach_suggestions(f, provider) {
		this.providers[f] = provider;
	}
	detach_suggestions(f) {
		delete this.providers[f];
	}
}

/** Fake dataset: XA with Region -> City -> District and postal codes. */
function dataset_responses() {
	const hierarchy = {
		supported: true,
		country_code: "xa",
		levels: [
			{ level: 1, label: "Region", target_field: "state" },
			{ level: 2, label: "City", target_field: "city" },
			{ level: 3, label: "District", target_field: "county" },
		],
		postal_codes: { available: true, target_field: "pincode" },
	};
	const options = {
		"1:": [
			{ value: "R1", label: "North Region" },
			{ value: "R2", label: "South Region" },
		],
		"2:R1": [
			{ value: "C1", label: "Alpha City", aliases: ["Alfa"] },
			{ value: "C2", label: "Beta City" },
		],
		"2:R2": [{ value: "C3", label: "Alpha City" }],
		"3:C1": [
			{ value: "D1", label: "East" },
			{ value: "D2", label: "West" },
		],
		"3:C2": [{ value: "D3", label: "Centre" }],
	};
	// like the server: `parent` may be the direct parent or any ancestor
	const level_of = (code) => {
		for (const key of Object.keys(options)) {
			if ((options[key] || []).some((o) => o.value === code))
				return Number(key.split(":")[0]);
		}
		return 0;
	};
	const options_under = (level, parent) => {
		if (level === 1) return options["1:"] || [];
		if (!parent) return [];
		let rows = [{ value: parent }];
		for (let lvl = level_of(parent) + 1; lvl <= level; lvl++) {
			rows = rows.flatMap((u) => options[`${lvl}:${u.value}`] || []);
		}
		return rows;
	};
	const postal = {
		"2:C1": ["1000"],
		"3:D1": ["1000"],
		"3:D2": ["1000"],
		"2:C2": ["2000", "2001"],
	};
	return {
		"geo_extension.api.get_hierarchy": ({ country }) =>
			country === "Testland" ? hierarchy : { supported: false, levels: [] },
		"geo_extension.api.get_options": ({ level, parent }) => options_under(level, parent),
		"geo_extension.api.get_postal_codes": ({ level, code }) => ({
			codes: postal[`${level}:${code}`] || [],
			level,
		}),
		"geo_extension.api.resolve": ({ names, levels }) => {
			const list = JSON.parse(names);
			const lvls = levels ? JSON.parse(levels) : list.map((_, i) => i + 1);
			const chain = [];
			let parent = "";
			for (let i = 0; i < list.length; i++) {
				if (!list[i]) break;
				const hit = options_under(lvls[i], parent).find(
					(o) => o.label.toLowerCase() === list[i].toLowerCase()
				);
				if (!hit) break;
				chain.push({ level: lvls[i], value: hit.value, label: hit.label });
				parent = hit.value;
			}
			return chain;
		},
	};
}

const tick = () => new Promise((r) => setTimeout(r, 5));

module.exports = { make_env, FakeAdapter, dataset_responses, tick };
