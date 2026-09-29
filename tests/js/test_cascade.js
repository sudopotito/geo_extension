const test = require("node:test");
const assert = require("node:assert/strict");
const { make_env, FakeAdapter, dataset_responses, tick } = require("./setup");

const FIELDS = ["state", "city", "county", "pincode", "address_line1"];

async function make_cascade(country = "Testland", values = {}) {
	const env = make_env({ responses: dataset_responses() });
	const adapter = new FakeAdapter(FIELDS);
	Object.assign(adapter.values, values);
	const cascade = new env.geo.GeoCascade({ country, adapter });
	await cascade.setup();
	return { env, adapter, cascade };
}

test("unsupported country leaves the form untouched", async () => {
	const { adapter, cascade } = await make_cascade("Atlantis", { city: "Somewhere" });
	assert.equal(cascade.supported, false);
	assert.deepEqual(cascade.level_fields, []);
	assert.deepEqual(adapter.labels, {});
	assert.equal(adapter.values.city, "Somewhere");
	assert.equal(cascade.handles("city"), false);
});

test("setup relabels fields and attaches suggestions", async () => {
	const { adapter, cascade } = await make_cascade();
	assert.deepEqual(cascade.level_fields, ["state", "city", "county"]);
	assert.deepEqual(adapter.labels, { state: "Region", city: "City", county: "District" });
	assert.deepEqual(Object.keys(adapter.providers).sort(), [
		"city",
		"county",
		"pincode",
		"state",
	]);
	assert.deepEqual(await adapter.providers.state(), [
		{ value: "R1", label: "North Region" },
		{ value: "R2", label: "South Region" },
	]);
	assert.deepEqual(await adapter.providers.city(), []); // no region selected yet
});

test("selecting a parent filters children and a different parent clears them", async () => {
	const { adapter, cascade } = await make_cascade();
	adapter.values.state = "North Region";
	await cascade.handle_change("state");
	assert.deepEqual(cascade.codes, ["R1", null, null]);
	assert.deepEqual(
		(await adapter.providers.city()).map((o) => o.value),
		["C1", "C2"]
	);

	adapter.values.city = "Beta City";
	await cascade.handle_change("city");
	adapter.values.county = "Centre";
	await cascade.handle_change("county");
	assert.deepEqual(cascade.codes, ["R1", "C2", "D3"]);

	adapter.values.state = "South Region";
	await cascade.handle_change("state");
	assert.deepEqual(cascade.codes, ["R2", null, null]);
	assert.equal(adapter.values.city, "");
	assert.equal(adapter.values.county, "");
	assert.deepEqual(
		(await adapter.providers.city()).map((o) => o.value),
		["C3"]
	);
});

test("free text keeps lower levels; clearing a level clears below", async () => {
	const { adapter, cascade } = await make_cascade();
	adapter.values.state = "North Region";
	await cascade.handle_change("state");
	adapter.values.city = "Alpha City";
	await cascade.handle_change("city");
	adapter.values.county = "East";
	await cascade.handle_change("county");

	adapter.values.city = "Alpha Cty"; // typo: not in the dataset
	await cascade.handle_change("city");
	assert.deepEqual(cascade.codes, ["R1", null, null]);
	assert.equal(
		adapter.values.county,
		"East",
		"manual edits never wipe what the user entered below"
	);

	adapter.values.city = "";
	await cascade.handle_change("city");
	assert.equal(adapter.values.county, "");
});

test("aliases and case/accents resolve to the same unit", async () => {
	const { adapter, cascade } = await make_cascade();
	adapter.values.state = "north région";
	await cascade.handle_change("state");
	assert.equal(cascade.codes[0], "R1");
	adapter.values.city = "ALFA";
	await cascade.handle_change("city");
	assert.equal(cascade.codes[1], "C1");
});

test("existing values are resolved on setup without changing them", async () => {
	const { adapter, cascade } = await make_cascade("Testland", {
		state: "South Region",
		city: "Alpha City",
		county: "Nowhere",
	});
	assert.deepEqual(cascade.codes, ["R2", "C3", null]);
	assert.deepEqual(adapter.log, []);
	assert.equal(adapter.values.county, "Nowhere");
});

test("postal code: unique fills, ambiguous suggests, manual is kept, stale auto value is retracted", async () => {
	const { adapter, cascade } = await make_cascade();
	adapter.values.state = "North Region";
	await cascade.handle_change("state");
	adapter.values.city = "Alpha City";
	await cascade.handle_change("city");
	assert.equal(adapter.values.pincode, "1000");
	assert.equal(cascade.auto_postal, "1000");

	adapter.values.county = "East"; // district inherits the city's code
	await cascade.handle_change("county");
	assert.equal(adapter.values.pincode, "1000");

	adapter.values.city = "Beta City"; // two codes: never guess
	await cascade.handle_change("city");
	assert.equal(adapter.values.pincode, "");
	assert.deepEqual(
		cascade.postal_options.map((o) => o.value),
		["2000", "2001"]
	);
	assert.deepEqual(await adapter.providers.pincode(), cascade.postal_options);

	adapter.values.pincode = "9999"; // typed by the user
	adapter.values.city = "Alpha City";
	await cascade.handle_change("city");
	assert.equal(adapter.values.pincode, "9999");

	adapter.values.state = "South Region"; // no postal data at all
	await cascade.handle_change("state");
	assert.equal(adapter.values.pincode, "9999");
});

test("clear_values resets levels and auto postal but not a manual postal code", async () => {
	const { adapter, cascade } = await make_cascade();
	adapter.values.state = "North Region";
	await cascade.handle_change("state");
	adapter.values.city = "Alpha City";
	await cascade.handle_change("city");
	assert.equal(adapter.values.pincode, "1000");
	await cascade.clear_values();
	assert.deepEqual(
		[adapter.values.state, adapter.values.city, adapter.values.pincode],
		["", "", ""]
	);
	assert.deepEqual(cascade.codes, [null, null, null]);

	adapter.values.pincode = "4321";
	await cascade.clear_values();
	assert.equal(adapter.values.pincode, "4321");
});

test("teardown restores labels and detaches suggestions", async () => {
	const { adapter, cascade } = await make_cascade();
	cascade.teardown();
	assert.deepEqual(adapter.labels, {});
	assert.deepEqual(adapter.providers, {});
	assert.equal(cascade.supported, false);
});

test("client caches option requests per country/level/parent", async () => {
	const { env, adapter, cascade } = await make_cascade();
	env.reset();
	await adapter.providers.state();
	await adapter.providers.state();
	await cascade.options_for(0);
	assert.equal(env.calls.filter((c) => c.method === "geo_extension.api.get_options").length, 1);
});

test("a superseded setup does not apply", async () => {
	const env = make_env({ responses: dataset_responses() });
	const adapter = new FakeAdapter(FIELDS);
	const cascade = new env.geo.GeoCascade({ country: "Testland", adapter });
	const pending = cascade.setup();
	cascade.teardown();
	await pending;
	await tick();
	assert.equal(cascade.supported, false);
	assert.deepEqual(adapter.labels, {});
});
