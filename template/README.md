# Contributing New Countries to Geo Extension

Geo Extension grows stronger when contributors like you add support for more countries.  
This guide will walk you through how to structure and submit your country’s administrative data — so users everywhere can enjoy cleaner, smarter address inputs.

## Before You Start

Before creating a new country folder, check if your country is already supported here:  
👉 [Supported Countries](https://github.com/sudopotito/geo_extension?tab=readme-ov-file#supported-countries)

If your country already exists, **you can still contribute** — by submitting **improvements, updates, or new levels** through a Pull Request (PR).  
Every contribution helps make the global address data more complete and accurate.

---

## 1. Folder Setup and Structure

All country data is stored under:

```
geo_extension/setup/data/countries/<xx>/
```

Where `xx` is your **country code** (based on Frappe’s Country Doctype).  
You can find it inside Frappe → _Country List_ → open your country → _Code_.

Start by copying the template folder:

```
template/xx/
```

Rename it to your country code (for example, `ph` for the Philippines).  
Your new folder should contain these files:

```
countries/
  xx/
    manifest.json
    level1.csv
    level2.csv
    level3.csv
```

All countries currently supported use a maximum of 3 levels. Please restrict your contribution to `level1.csv`, `level2.csv`, and `level3.csv`.

---

## 2. Understanding the Hierarchy

Each CSV file represents one level of your country’s geographic structure.

| Level   | Description | Example                  |
| ------- | ----------- | ------------------------ |
| Level 1 | Top level   | Province, Region, State  |
| Level 2 | Sub-level   | City, Municipality       |
| Level 3 | Lower level | District, Ward, County |

Every lower level must reference the **parent level** through a `parent_code` column.  
This Geo Extension supports a maximum of 3 administrative levels (State, City, County/District) which map to the default Frappe Address fields.

---

## 3. The `manifest.json` File

This file connects your CSV levels with Frappe’s Address fields and describes your dataset.

Example:

```json
{
  "country_code": "ph",
  "author": "sudo potito <sudopotito@gmail.com> | https://github.com/sudopotito/geo_extension",
  "version": "1.0.0",
  "description": "Philippine Standard Geographic Hierarchy - 81 Provinces, 146 Cities & 1,488 Municipalities and 42,004 Counties",
  "source": "https://psa.gov.ph/classification/psgc",
  "levels": [
    {
      "file": "level1.csv",
      "label": "Province",
      "target_field": "state"
    },
    {
      "file": "level2.csv",
      "label": "City/Municipality",
      "target_field": "city",
      "parent_level": 1
    },
    {
      "file": "level3.csv",
      "label": "County",
      "target_field": "county",
      "parent_level": 2
    }
  ]
}
```

### Field Notes

- **`country_code`**: Must match the folder name and Frappe Country code.
- **`author`**: Use the format `Name <email> | link`. This lets us credit you properly.
- **`version`**: Start with `1.0.0`.
- **`description`**: Add a clear summary (e.g., number of divisions).
- **`source`**: Always cite an official or verifiable data source.
- **`levels`**: Defines the order, label, and field mapping for each CSV.

---

## 4. CSV File Format

Each level file represents one hierarchy layer. Keep your formatting **simple and consistent**.

### Level 1 (Top Level)

**Headers:**

```
code,name
```

Example:

```
0128,Ilocos Norte
0129,Ilocos Sur
0133,La Union
0155,Pangasinan
```

### Level 2 and Below

**Headers:**

```
parent_code,code,name
```

Example (`level2.csv`):

```
parent_code,code,name
0155,015501000,Agno
0155,015502000,Aguilar
0155,015503000,Alaminos City
```

### Recommended Editing

It’s best to **use Google Sheets** for editing your CSVs, since Excel often auto-formats or removes leading zeros.  
If you still prefer Excel, make sure **auto-formatting is disabled**, and double-check that `code` and `name` columns remain exact.

**Guidelines:**

- Each `parent_code` must exist in the parent CSV.
- Codes must be **unique and stable** (use government/official codes if available).
- Save files as **UTF-8 without BOM**.

---

## 5. Testing Your Data

Before submitting, make sure your contribution works inside Frappe:

1. Install your updated Geo Extension app.
2. Create a new Address record.
3. Set **Country** to your new country.
4. Verify that:
   - Level fields appear correctly in order.
   - Selecting one field filters the next level properly.

---

## 6. Submitting Your Pull Request

When your country data is ready, submit a PR with:

**Title:**  
`feat: New Country <Country Name> (<code>) administrative divisions`

**Description:**

- Summary of your contribution.
- Levels and target fields used.
- Source link.
- Author information.

Your PR helps improve the experience for frappe users around the world — and you’ll be credited as a contributor in the project.

---

## 7. Review Process

We’ll verify:

- Folder and `country_code` correctness.
- Hierarchy and parent relationships.
- CSV formatting and encoding.
- Valid and verifiable data source.

---

## 9. Final Words

Thank you in advance for contributing to Geo Extension!
Every country you add helps make addresses easier, cleaner, and more accurate for users worldwide.  
Even if your country is already supported, your updates and improvements are always welcome.  
Your effort makes a global difference — one CSV at a time.
