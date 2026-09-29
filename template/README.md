# Contributing a Country Dataset

A country dataset is a folder with one small JSON file and a few CSV files. You do not need to know Frappe, only where to find your country's list of regions and cities.

## Before you start

- Check the [supported countries](../README.md#supported-countries). An existing dataset can still be improved (more levels, better coverage, corrections, postal codes).
- Find an official or verifiable source (statistics office, postal service, open-data portal) whose license allows redistribution. GeoNames (CC BY 4.0) is fine when nothing official is downloadable.
- Decide which administrative levels are *useful on an address*. Three levels is typical, six is the maximum. Skip tiers nobody writes on an envelope.

## 1. Create the folder

Datasets live in `geo_extension/setup/data/countries/<cc>/` where `<cc>` is the lowercase ISO 3166-1 alpha-2 code (Frappe → *Country* → your country → *Code*).

```
<cc>/
├── manifest.json
├── level1.csv
├── level2.csv
├── level3.csv          (optional, up to level6.csv)
└── postal_codes.csv    (optional)
```

Start by copying [`template/xx/`](xx). If GeoNames covers your country well, you can instead add it to `tools/geonames/countries.json` and run `python tools/geonames/build_dataset.py <cc> --out geo_extension/setup/data/countries` (see [tools/README.md](../tools/README.md)).

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

| Property | Meaning |
| -------- | ------- |
| `country_code` | Must equal the folder name. |
| `levels` | Ordered top-down; each level nests inside the previous one. |
| `levels[].label` | What users see as the field label (*Province*, *Prefecture*, *Barangay*, …). |
| `levels[].target_field` | Native Address field that stores the value: `state`, `county`, `city` or `address_line2`. Each may be used once. |
| `postal_codes` | Optional. `pattern` is a regular expression every code must match; it catches typos early. |
| `name`, `description`, `version`, `source`, `license`, `author` | Metadata shown by `bench geo-extension list` and used to credit you. |

**Choosing the field mapping.** Map each level to the native field closest in meaning; the label tells users what it holds. Examples:

| Country | Mapping |
| ------- | ------- |
| Philippines | Province → `state`, City/Municipality → `city`, Barangay → `county` |
| United States | State → `state`, County → `county`, City → `city` |
| Türkiye | Province → `state`, District → `city` |
| Singapore | Planning Area → `city` |

If a country has more useful levels than fields, use `address_line2` for the lowest one or leave a level out.

## 3. Fill the level files

Level 1 has two columns plus the optional `aliases`; every lower level adds `parent_code` in front:

```csv
code,name,aliases
NR,Northern Region,North
CR,Central Region,
```

```csv
parent_code,code,name,aliases
NR,NR01,Northport,North Port
CR,CR01,Capital City,City of Capital|Capitol
```

- `code` is the stable identifier: unique within its file, letters, digits, `.`, `_`, `-`. Use official codes when they exist; they survive renames.
- `name` is what users see and what gets stored. Use the official spelling, with accents.
- `parent_code` must exist in the file above.
- `aliases` (optional) lists alternative spellings separated by `|`: old names, "X City" for "City of X", local-language variants. They are matched when typed but never displayed. Do not reuse a sibling's name as an alias.
- Save as UTF-8. Google Sheets exports are fine; in Excel make sure leading zeros in codes survive.

## 4. Add postal codes (optional)

`postal_codes.csv` attaches codes to units at any level, one row per (unit, code):

```csv
level,code,postal_code
2,NR01,1000
2,SR01,3000
2,SR01,3001
3,CR01-01,2001
```

The app looks at the deepest selected unit first, then its parent, and so on. One code fills *Postal Code* automatically; several are offered as suggestions; nothing is guessed. Only add codes you are sure about.

## 5. Validate

```bash
bench geo-extension validate <cc>
# or, without a bench:
python -m geo_extension.geo.validate --path geo_extension/setup/data/countries/<cc>
```

Fix every `ERROR`. Warnings about units with no children are expected for partial coverage.

## 6. Try it

`bench --site <site> clear-cache`, open *Address → New*, choose your country, and check the labels, the cascading lists and the postal codes.

## 7. Open a pull request

Title `feat(data): add <Country> (<cc>)` (or `fix(data): …` for improvements). Say what the dataset covers, link the source, state the license and mention anything you deliberately left out. The pull request template asks for exactly these. Thank you for making address entry easier for everyone using Frappe.
