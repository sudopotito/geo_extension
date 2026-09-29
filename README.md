<div align="center">
  <a href="https://frappe.io">
    <img src=".github/logo.svg" height="80" width="80" alt="Octicon Globe">
  </a>

  <h1>Geo Extension</h1>
  <h4>Fast, consistent address entry for Frappe / ERPNext</h4>

  <img src=".github/hero.gif" alt="Geo Extension: Iloilo > City of Iloilo > San Rafael selected step by step with the postal code filled automatically, then a United States address" width="100%" />
  <p><sub>Also available as <a href=".github/hero.mp4">hero.mp4</a>. Screenshots in <a href=".github/screenshots">.github/screenshots</a>.</sub></p>

<br>

</div>

---

Geo Extension turns the native **Address** form into a cascading, country-aware selector, the way a good e-commerce checkout works:

```
Country → State / Province → City → Lower level → Postal code
```

Each field only offers what belongs to the selection above it, the postal code is filled in when it can be determined reliably, and users only type the truly local part of the address.

- **Nothing changes in your DocType.** No Custom Fields, no Property Setters. The native fields (`state`, `county`, `city`, `address_line2`, `pincode`) are reused and stay plain text.
- **Assists, never restricts.** Every field remains free text. Unknown values are accepted, auto-filled values can be edited, and unsupported countries behave exactly like stock Frappe.
- **Works everywhere addresses are entered.** The Address form, quick-entry dialogs (including ERPNext's Customer and Supplier quick entry) and the portal's Address web form.
- **Country-agnostic.** Hierarchies, labels and postal codes are data. Adding a country never touches code.

## Supported Countries

|  |  |  |  |  |
| --- | --- | --- | --- | --- |
| 🇦🇺 Australia | 🇧🇩 Bangladesh | 🇧🇷 Brazil | 🇨🇦 Canada | 🇪🇬 Egypt |
| 🇫🇷 France | 🇩🇪 Germany | 🇮🇳 India | 🇮🇩 Indonesia | 🇮🇹 Italy |
| 🇰🇪 Kenya | 🇲🇾 Malaysia | 🇲🇽 Mexico | 🇳🇵 Nepal | 🇳🇱 Netherlands |
| 🇳🇿 New Zealand | 🇳🇬 Nigeria | 🇵🇰 Pakistan | 🇵🇭 Philippines | 🇸🇦 Saudi Arabia |
| 🇸🇬 Singapore | 🇿🇦 South Africa | 🇪🇸 Spain | 🇱🇰 Sri Lanka | 🇨🇭 Switzerland |
| 🇹🇭 Thailand | 🇹🇷 Türkiye | 🇦🇪 United Arab Emirates | 🇬🇧 United Kingdom | 🇺🇸 United States |

Each country's hierarchy, record counts, source and license are in its `manifest.json`; `bench geo-extension list` prints them for your bench. Eighteen of the thirty ship postal codes.

Your country is missing or incomplete? Datasets are plain CSV files and [contributing one](template/README.md) needs no Frappe knowledge. More countries are added with every release.

## Installation

Frappe Framework v15 or v16, with or without ERPNext.

```bash
bench get-app https://github.com/sudopotito/geo_extension
bench --site your-site.localhost install-app geo_extension
```

That is all. Open any Address, choose a supported country and the level fields turn into cascading selectors.

<a href="https://frappecloud.com/dashboard/signup?product=geo_extension" target="_blank">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://frappe.io/files/try-on-fc-white.png">
    <img src="https://frappe.io/files/try-on-fc-black.png" alt="Try on Frappe Cloud" height="28" />
  </picture>
</a>

**Upgrading from 1.x:** version 1.x customised the Address DocType. The first `bench migrate` after updating runs a one-time patch that removes those customisations and copies values from the old `village` field into `county` where it was empty. The 1.x endpoints under `geo_extension.geo_extension.locations` were replaced by `geo_extension.api`.

## How It Works

1. **Country** moves directly below *Address Type* so it is chosen first. The level fields are reordered top-down and relabelled with the country's own terms (*Province*, *Bundesland*, *Barangay*). Nothing is hidden.
2. Each level field gets a dropdown listing only the children of the unit selected above it. Typing filters the list; matching ignores case and accents and accepts known aliases ("Iloilo City" finds "City of Iloilo").
3. Picking a **different** unit clears the levels below it. Text that matches nothing is kept as typed and lower levels are left alone, so fixing a spelling by hand never wipes the rest of the address.
4. **Postal code:** exactly one known code for the selection fills `pincode`; several are offered as suggestions; a code typed by the user is never overwritten.
5. Existing addresses are resolved back to dataset units when opened, so the dropdowns keep filtering correctly.

## Beyond the Address Form

The selector and the API are independent of the Address integration.

**API** (read-only, guest accessible, `country` is a name or ISO code):

| Method | Returns |
| ------ | ------- |
| `geo_extension.api.get_hierarchy(country)` | levels with labels and native field mapping, postal code availability |
| `geo_extension.api.get_options(country, level, parent=None, txt=None)` | children of `parent` at `level` |
| `geo_extension.api.resolve(country, names)` | the chain of units matching a list of names, top level first |
| `geo_extension.api.get_postal_codes(country, level, code)` | postal codes of a unit or its nearest ancestor that has any |
| `geo_extension.api.search(country, txt, level=None)` | units at any level matching `txt`, each with its full path |
| `geo_extension.api.get_supported_countries()` | metadata of every installed dataset (logged-in users) |

```bash
curl "https://your-site/api/method/geo_extension.api.get_options?country=ph&level=2&parent=0603000000"
```

**Another DocType** with fields named like the native ones (`state`, `county`, `city`, `address_line2`, `pincode`):

```js
frappe.ui.form.on("Delivery Point", {
	async onload_post_render(frm) {
		frm.geo = new frappe.geo_extension.GeoCascade({
			country: frm.doc.country,
			adapter: new frappe.geo_extension.FormAdapter(frm),
		});
		await frm.geo.setup();
	},
	state: (frm) => frm.geo.handle_change("state"),
	city: (frm) => frm.geo.handle_change("city"),
});
```

**Dialogs and Web Forms:** quick-entry dialogs and standard Address web forms are wired automatically. Any other dialog or web form with those fields needs one call:

```js
frappe.geo_extension.attach_to_field_group(frappe.web_form); // or a frappe.ui.Dialog
```

On website pages load the selector first with `frappe.require("/assets/geo_extension/js/geo_selector.js")`.

**Private datasets:** point `geo_extension_dataset_roots` in `site_config.json` at directories laid out like `setup/data/countries` to add or override countries without forking the app.

## Contributing

- **Geographic data:** copy [template/xx](template/xx), fill the CSV files, run `bench geo-extension validate <cc>` and open a pull request. The [contributor guide](template/README.md) walks through it step by step. Shipped datasets are generated from official sources or GeoNames by the scripts in [tools/](tools/).
- **Code:** see [AGENTS.md](AGENTS.md) for the invariants, the map of the code base and the test commands.

```bash
bench --site your-site.localhost run-tests --app geo_extension
node --test "tests/js/test_*.js"
pre-commit run --all-files
```

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
