# Geo Extension — Maintainer & Agent Notes

Short, accurate orientation for anyone (human or AI) working on this repository. The README is the user-facing documentation; this file records the invariants that must not be broken.

## What the app does

Turns the native Frappe **Address** form into a cascading, country-aware selector (Country → level 1 → level 2 → … → postal code) without changing the Address DocType. Everything is data-driven by per-country datasets.

## Invariants

1. **No schema or layout customisation.** `install.py` must never create Custom Fields or Property Setters. It only *removes* leftovers from versions ≤ 1.4 (`remove_legacy_customizations`, idempotent, also run on uninstall).
2. **Assist, never restrict.** Fields stay `Data`. Suggestions are attached at runtime (Awesomplete on the plain input). Free text must always be accepted and saved.
3. **Country-agnostic core.** No `if country == "..."` anywhere. Country differences live in `setup/data/countries/<cc>/manifest.json` + CSV files.
4. **Bounded responses.** `get_options` for level > 1 requires a parent; the browser never receives a whole level of a large dataset (Philippine barangays: 42k rows).
5. **Soft failure.** Broken or missing datasets make a country "unsupported"; they never raise into the Address form. Loud checking belongs in the validator.

## Map

| Path | Role |
| ---- | ---- |
| `geo_extension/geo/dataset.py` | Load + index a dataset (`CountryDataset`, `Unit`, `Level`), per-process cache invalidated by file mtime, no Frappe dependency. |
| `geo_extension/geo/validate.py` | Validator with file/line issues; `python -m geo_extension.geo.validate` works without a site. |
| `geo_extension/api.py` | Whitelisted endpoints: `get_hierarchy`, `get_options`, `resolve`, `get_postal_codes` (guest, read-only), `get_supported_countries`. |
| `geo_extension/commands/__init__.py` | `bench geo-extension validate|list`. |
| `geo_extension/install.py` | Legacy cleanup hooks only. |
| `geo_extension/geo_extension/locations.py` | Deprecated shim over `api.py` for the 1.x endpoints. Remove in a later major release. |
| `geo_extension/public/js/geo_selector.js` | `frappe.geo_extension`: cached client, `GeoCascade`, `FormAdapter`, `WebFormAdapter`, `attach_suggestions`. |
| `geo_extension/public/js/address.js` | Address form wiring: build cascade on load / country change, DOM reordering of fields, level change events. |
| `geo_extension/setup/data/countries/<cc>/` | Shipped datasets. |
| `geo_extension/tests/` | Unit tests (dataset, validator; no site) and integration tests (API, install, Address). Fixtures in `tests/data/countries/x?`. |
| `template/` | Contributor template dataset + guide. |

## Cascade semantics (geo_selector.js)

- `codes[i]` holds the selected unit code per level (`null` = unknown/manual).
- `handle_change(field)`: resolve the typed value against the options of that level; a *different* resolved unit or an empty value clears the levels below; unresolved text keeps them.
- Postal: exactly one code → fill `pincode` if empty or still equal to `auto_postal`; several → suggestions only; none → retract an auto-filled value. Manual values are never touched.
- `teardown()` restores labels and suggestion lists; a `_generation` counter cancels superseded `setup()` calls.

## Commands

```bash
bench --site <site> run-tests --app geo_extension
python -m unittest geo_extension.tests.test_dataset geo_extension.tests.test_validate   # no site needed
bench geo-extension validate [cc ...] [--strict] [--path DIR]
pre-commit run --all-files
```

## Branching

`enhancement` → `develop` → `main` (releases are tagged from `main` by semantic-release). Keep `develop` and `main` free of direct commits.
