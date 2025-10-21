# Contributing New Countries to Geo Extension

You can help make Geo Extension support more countries by adding your country’s administrative divisions. Follow these simple steps to contribute properly and ensure your data integrates smoothly.

---

## 1. Folder and Structure

Country data is stored here:

```
geo_extension/setup/data/countries/<xx>/
```

- `xx` = the **country code** (2-letter ISO code used in Frappe’s Country Doctype).
- You can check this code inside Frappe → _Country List_ → open your country → _Code_.

To start, copy the folder from:

```
template/xx/
```

Rename it to your country code (e.g., `ph` for the Philippines).  
Your new folder will contain:

```
countries/
  xx/
    manifest.json
    level1.csv
    level2.csv
    level3.csv
```

You can add more levels if needed (e.g., `level4.csv`).

---

## 2. Understanding the Hierarchy

The CSV levels represent the geographic hierarchy of your country.

- **Level 1** – top level (e.g., State, Region, or Province)
- **Level 2** – next level (e.g., City or Municipality)
- **Level 3** – lower level (e.g., Barangay, District, or Ward)

Each lower level must reference the parent level through the `parent_code` field.  
You can define as many levels as your country’s geography requires.

---

## 3. The `manifest.json` File

This file defines your country’s metadata and how each level connects to Frappe’s Address fields.

Example:

```json
{
  "country_code": "ph",
  "author": "David Webb Espiritu <davidwebbespiritu@gmail.com> | https://www.linkedin.com/in/davidwebbespiritu",
  "version": "1.0.0",
  "description": "Cities and Municipalities of the Philippines - 146 Cities & 1,488 Municipalities",
  "source": "https://psa.gov.ph/classification/psgc",
  "levels": [
    { "file": "level1.csv", "label": "Province", "target_field": "state" },
    {
      "file": "level2.csv",
      "label": "City/Municipality",
      "target_field": "city",
      "parent_level": 1
    },
    {
      "file": "level3.csv",
      "label": "Barangay",
      "target_field": "barangay",
      "parent_level": 2
    }
  ]
}
```

### Field Notes

- **`country_code`**: Must match the folder name and Frappe Country code.
- **`author`**: Use your full name, email, and link (same format shown).
- **`version`**: Start with `1.0.0`.
- **`description`**: Include the total count or short description of your dataset.
- **`source`**: Provide an official reference (e.g., national statistics, open data portal).
- **`levels`**: Define your hierarchy and how each file maps to Frappe Address fields.

---

## 4. CSV File Format

### Level 1 (Top Level)

`level1.csv` should only have:

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

From level 2 onward, use:

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

**Rules:**

- Each `parent_code` must exist in the parent CSV.
- `code` should be unique.
- Use official government codes if available.

---

## 5. Custom Address Fields

Some countries need extra Address fields like _District_ or _Barangay_.  
If your country needs one, you can define it in the app setup script.

Example (`install.py`):

```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install(force: bool = False):
    create_custom_fields({
        "Address": [
            {
                "fieldname": "barangay",
                "label": "Barangay",
                "fieldtype": "Autocomplete",
                "insert_after": "city",
            }
        ]
    }, ignore_validate=True, update=True)
```

Then, in your `manifest.json`, set `"target_field": "barangay"` for that level.

If you add a custom field, mention it clearly in your pull request so it can be reviewed.

---

## 6. Testing Your Data

Before submitting your contribution, verify it works in Frappe:

1. Install the app with your new data.
2. Create a new Address and select your country.
3. Check that:
   - Levels appear correctly and in the right order.
   - Selecting a value in one field filters the next level.
   - Any new field you added works as expected.

---

## 7. Submitting a Pull Request

When your data is ready, create a Pull Request with the following title and details:

**Title:**  
`feat(country): add <Country Name> (<code>) administrative divisions`

**Include in the PR description:**

- Summary of added levels and fields.
- Source link.
- Author information.
- Note if you added a custom field.

---

## 8. Review Guidelines

Maintainers will verify:

- Folder and country code match.
- Proper hierarchy and parent relationships.
- CSV structure and encoding (UTF-8).
- Source credibility and completeness.
- Custom fields, if any, are correctly defined.

---

Once approved, your country will be added to Geo Extension — helping users get structured, accurate, and easy-to-use address data worldwide.
