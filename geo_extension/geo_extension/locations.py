import os, json, csv
import frappe

_COUNTRIES_DIR = ("geo_extension", "setup", "data", "countries")


def _country_code_for(country_name: str) -> str:
    """
    Address.country is a Link to Country. Pull Country.code exactly as-is.
    Ex: "Philippines" -> "ph" (if that's what you set in Country.code)
    """
    if not country_name:
        frappe.throw("country is required")
    code = frappe.db.get_value("Country", country_name, "code")
    if not code:
        frappe.throw(f"No Country.code for '{country_name}'")
    return code  # No case normalization, use as-is


def _country_base_path(code: str) -> str:
    return frappe.get_app_path(*_COUNTRIES_DIR, code)


def _load_manifest(base_path: str) -> dict:
    mf = os.path.join(base_path, "manifest.json")
    if not os.path.exists(mf):
        frappe.throw(f"Manifest not found: {mf}")
    with open(mf, encoding="utf-8") as f:
        return json.load(f)


@frappe.whitelist(allow_guest=True)
def get_levels(country: str):
    """
    Return levels for the selected country (per manifest).
    """
    code = _country_code_for(country)
    base = _country_base_path(code)
    if not os.path.isdir(base):
        frappe.throw(f"Country folder not found: {base}")

    m = _load_manifest(base)
    out = []
    for i, lvl in enumerate(m.get("levels", []), start=1):
        out.append(
            {
                "index": i,
                "label": lvl["label"],
                "target_field": lvl["target_field"],
                "parent_level": lvl.get("parent_level"),
                "file": lvl["file"],
            }
        )
    return out


@frappe.whitelist(allow_guest=True)
def get_level_options(country: str, level_index: int, parent_code: str = None):
    """
    Return [{label, value}] for the requested level, filtered by parent_code if defined.
    CSV headers are assumed: code,name,(parent_code?)
    """
    code = _country_code_for(country)
    base = _country_base_path(code)
    if not os.path.isdir(base):
        frappe.throw(f"Country folder not found: {base}")

    m = _load_manifest(base)
    try:
        level = m["levels"][int(level_index) - 1]
    except (IndexError, ValueError):
        frappe.throw("Invalid level_index")

    csv_path = os.path.join(base, level["file"])
    if not os.path.exists(csv_path):
        frappe.throw(f"Data file missing: {csv_path}")

    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # If this level depends on a parent, filter by exact parent_code
    if level.get("parent_level"):
        if not parent_code:
            return []
        rows = [r for r in rows if (r.get("parent_code") or "") == parent_code]

    return [{"label": r["name"], "value": r["code"]} for r in rows]
