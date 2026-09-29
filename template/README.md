# Contributing a Country Dataset

Geo Extension grows one country at a time, and every dataset is plain files: a small JSON manifest and a few CSV files. You do not need to know Frappe to contribute.

## Before you start

- Check the [supported countries](../README.md#supported-countries). If yours exists you can still improve it (more levels, better coverage, corrections, postal codes).
- Find an official or verifiable source (statistics office, postal service, open-data portal) whose license allows redistribution.
- Decide which administrative levels are *useful for addresses*. You do not have to model every government tier; three levels is typical, six is the maximum.

## 1. Create the directory

Datasets live in `geo_extension/setup/data/countries/<cc>/` where `<cc>` is the lowercase ISO 3166-1 alpha-2 code (Frappe → *Country* list → your country → *Code*).

Copy this template:

```
template/xx/  →  geo_extension/setup/data/countries/<cc>/
```

Or generate the directory: if your country is well covered by GeoNames, add it to `tools/geonames/countries.json` and run `python tools/geonames/build_dataset.py <cc> --out geo_extension/setup/data/countries`. If an official statistics office publishes a downloadable list, a small script like `tools/psgc/build_dataset.py` (Philippines) or `tools/datagovsg/build_dataset.py` (Singapore) is the preferred route because it makes future updates reproducible. Hand-maintained CSVs are fine too.

```
<cc>/
├── manifest.json
├── level1.csv
├── level2.csv
├── level3.csv          (optional, up to level6.csv)
└── postal_codes.csv    (optional)
```

## 2. Describe the hierarchy in `manifest.json`

```json
{
  "country_code": "xx",
  "name": "Exampleland",
  "description": "Exampleland: 3 regions, 6 cities and 8 districts.",
  "version": "1.0.0",
  "source": "https://statistics.example.gov/administrative-divisions",
  "license": "CC BY 4.0",
  "author": "Your Name <you@example.com> | https://github.com/you",
  "levels": [
    { "file": "level1.csv", "label": "Region", "target_field": "state" },
    { "file": "level2.csv", "label": "City", "target_field": "city" },
    { "file": "level3.csv", "label": "District", "target_field": "county" }
  ],
  "postal_codes": { "file": "postal_codes.csv", "pattern": "^[0-9]{4}$" }
}
```

| Property | Required | Meaning |
| -------- | -------- | ------- |
| `country_code` | yes | Must equal the directory name. |
| `levels` | yes | Ordered top-down. Each level nests inside the previous one. |
| `levels[].file` | yes | CSV file name inside the directory. |
| `levels[].label` | yes | What users see as the field label (`Province`, `Prefecture`, `Barangay`, …). |
| `levels[].target_field` | yes | Native Address field that stores the value: `state`, `county`, `city` or `address_line2`. Each may be used once. |
| `name`, `description`, `version`, `source`, `license`, `author` | recommended | Metadata shown in `bench geo-extension list` and used to credit you. |
| `postal_codes.file` | optional | Postal code file (see step 4). |
| `postal_codes.pattern` | optional | Regular expression every postal code must match; catches typos early. |

### Choosing the field mapping

Map each level to the native field that comes closest in meaning. The label tells users what the field means, so a UK dataset can put counties in `county` while a Philippine dataset puts barangays there. Common patterns:

| Country | Mapping |
| ------- | ------- |
| Philippines | Province → `state`, City/Municipality → `city`, Barangay → `county` |
| United States | State → `state`, County → `county`, City → `city` |
| Japan | Prefecture → `state`, City → `city`, Ward → `county` |
| Singapore | Planning Area → `city` |

If a country has more useful levels than fields, use `address_line2` for the lowest one, or leave a level out (top-level regions that are implied by the province are usually not worth a field).

## 3. Fill the level files

**Level 1** has two columns (plus the optional `aliases`):

```csv
code,name,aliases
NR,Northern Region,North
CR,Central Region,
```

**Every lower level** has three; `parent_code` references the `code` of the level above:

```csv
parent_code,code,name,aliases
NR,NR01,Northport,North Port
NR,NR02,Highfield,
CR,CR01,Capital City,City of Capital|Capitol
```

Rules:

- `code` is the stable identifier: unique within its file, only letters, digits, `.`, `_`, `-`. Use official codes when they exist (PSGC, FIPS, INSEE, …); they survive renames.
- `name` is what users see and what gets stored in the Address. Use the official spelling, with accents.
- Every `parent_code` must exist in the parent file.
- `aliases` (optional column) lists alternative spellings separated by `|`: old official names, "X City" for "City of X", local-language variants. Users who type an alias get the unit; aliases are searchable but never displayed. Do not add an alias that is also the name of a sibling.
- Save as UTF-8 (a BOM is tolerated). Google Sheets exports are fine; if you use Excel, make sure leading zeros in codes are not stripped.
- Extra columns are ignored, but keep files small: they are versioned in Git.

## 4. Add postal codes (optional)

`postal_codes.csv` attaches postal codes to units at any level. One row per (unit, postal code):

```csv
level,code,postal_code
2,NR01,1000
3,CR01-01,2001
2,SR01,3000
2,SR01,3001
```

How the app uses it:

- The deepest selected unit is looked up first; if it has no rows, its parent is used, then the grandparent.
- One matching code fills `Postal Code` automatically. Several codes are offered as suggestions and the user picks or types. Nothing is guessed.
- So: if postal codes depend on the city, add rows for level 2; if they depend on a smaller area, add rows for level 3; if a city has many codes, add them all. Leave out anything you are not sure about.

## 5. Validate

```bash
bench geo-extension validate <cc>
# or, without a bench:
python -m geo_extension.geo.validate --path geo_extension/setup/data/countries/<cc>
```

Fix every `ERROR`. Warnings about "no children" are expected for partial datasets; everything else is worth a look. `--strict` treats warnings as errors.

## 6. Test in Frappe

1. `bench --site <site> clear-cache`
2. Open *Address → New*, choose your country.
3. Check the field labels and order, that each level only lists children of the selection above, and that postal codes behave as expected.
4. `bench --site <site> run-tests --app geo_extension` (the suite validates every shipped dataset).

## 7. Submit a pull request

**Title:** `feat(data): add <Country> (<cc>)` or `fix(data): …` for improvements.

**Description:** what the dataset covers (levels, counts, coverage), the source link and license, and anything you deliberately left out.

We check the manifest, hierarchy integrity, encoding and that the source is verifiable. Thank you for making address entry easier for everyone using Frappe.
