// attach_to_field_group: wiring for dialogs and Web Forms (frappe.ui.FieldGroup look-alikes).
const test = require("node:test");
const assert = require("node:assert/strict");
const { make_env, dataset_responses, tick } = require("./setup");

/** Minimal FieldGroup: fields_dict of controls with df.change, get_value/set_value like Frappe's. */
function make_group(fieldnames, values = {}) {
	const group = { fields_dict: {}, values: { ...values } };
	for (const name of fieldnames) {
		const ctrl = {
			df: { fieldname: name, label: name },
			labels: [],
			set_label(label) {
				this.df.label = label;
				this.labels.push(label);
			},
			$input: null,
		};
		group.fields_dict[name] = ctrl;
	}
	group.get_value = (f) => group.values[f];
	// Frappe controls call df.change after a value is set, also for programmatic set_value
	group.set_value = async (f, v) => {
		group.values[f] = v;
		const ctrl = group.fields_dict[f];
		if (ctrl && ctrl.df.change) await ctrl.df.change();
	};
	group.change = (f, v) => group.set_value(f, v); // what a user edit does
	return group;
}

test("files inlined into Web Forms are safe for Frappe's Jinja rendering", () => {
	// hooks.webform_include_js files go through frappe.render_template, which
	// rejects ".__" and would interpret Jinja delimiters.
	const fs = require("node:fs");
	const path = require("node:path");
	const dir = path.join(__dirname, "..", "..", "geo_extension", "public", "js");
	for (const file of ["geo_selector.js", "address_web_form.js"]) {
		const src = fs.readFileSync(path.join(dir, file), "utf8");
		for (const bad of ["{{", "{%", "{#", ".__"]) {
			assert.ok(!src.includes(bad), `${file} contains ${JSON.stringify(bad)}`);
		}
	}
});

test("dialog without address fields is left alone", () => {
	const env = make_env({ responses: dataset_responses() });
	const group = make_group(["subject", "country"]);
	assert.equal(env.geo.attach_to_field_group(group), null);
	assert.equal(group.__geo_cascade, undefined);
});

test("labels follow the country and a selection cascades in a Web Form-like group", async () => {
	const env = make_env({ responses: dataset_responses() });
	const group = make_group(["country", "state", "city", "pincode"], { country: "Testland" });
	const state = env.geo.attach_to_field_group(group);
	assert.ok(state && state.cascade);
	await state.ready;
	assert.equal(group.fields_dict.state.df.label, "Region");
	assert.equal(group.fields_dict.city.df.label, "City");
	assert.equal(group.fields_dict.country.df.label, "country"); // untouched

	await group.change("state", "North Region");
	await tick();
	await group.change("city", "Alpha City");
	await tick();
	assert.equal(group.values.pincode, "1000"); // unique postal code filled

	// selecting another region clears the city and the auto-filled postal code
	await group.change("state", "South Region");
	await tick();
	assert.equal(group.values.city, "");
	assert.equal(group.values.pincode, "");
});

test("changing the country clears the levels and restores labels when unsupported", async () => {
	const env = make_env({ responses: dataset_responses() });
	const group = make_group(["country", "state", "city", "pincode"], { country: "Testland" });
	const state = env.geo.attach_to_field_group(group);
	await state.ready;
	await group.change("state", "North Region");
	await tick();
	await group.change("city", "Alpha City");
	await tick();
	assert.equal(group.values.pincode, "1000");

	await group.change("country", "Nowhere");
	await state.ready;
	await tick();
	assert.equal(group.values.state, "");
	assert.equal(group.values.city, "");
	assert.equal(group.values.pincode, "");
	assert.equal(group.fields_dict.state.df.label, "state");
	assert.equal(state.cascade.supported, false);

	// a typed value in an unsupported country is kept as is (native behaviour)
	await group.change("state", "Somewhere");
	assert.equal(group.values.state, "Somewhere");
});

test("attaching twice returns the same state", () => {
	const env = make_env({ responses: dataset_responses() });
	const group = make_group(["country", "state"]);
	const a = env.geo.attach_to_field_group(group);
	const b = env.geo.attach_to_field_group(group);
	assert.equal(a, b);
});
