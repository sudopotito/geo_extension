import os, json, csv
import frappe

_COUNTRIES_DIR = ("geo_extension", "setup", "data", "countries")

# --- internals ---


def _country_code_for(country_name: str) -> str:
    """Use Country.code exactly as-is (no case changes)."""
    if not country_name:
        frappe.throw("country is required")
    code = frappe.db.get_value("Country", country_name, "code")
    if not code:
        frappe.throw(f"No Country.code found for '{country_name}'")
    return code


def _country_base_path(code: str) -> str:
    return frappe.get_app_path(*_COUNTRIES_DIR, code)


def _load_manifest(base_path: str) -> dict:
    mf = os.path.join(base_path, "manifest.json")
    if not os.path.exists(mf):
        frappe.throw(f"Manifest not found: {mf}")
    with open(mf, encoding="utf-8") as f:
        return json.load(f)


def _read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        frappe.throw(f"Data file missing: {path}")
    # Support BOM + trim spaces
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, skipinitialspace=True))


def _ensure_headers(rows: list[dict], required: tuple[str, ...], path: str):
    if not rows:
        return
    headers = {(k or "").strip() for k in rows[0].keys()}
    missing = [h for h in required if h not in headers]
    if missing:
        raise frappe.ValidationError(
            f"CSV '{path}' is missing required column(s): {', '.join(missing)}. "
            f"Expected exactly: {', '.join(required)}"
        )


# --- API ---


@frappe.whitelist(allow_guest=True)
def get_levels(country: str):
    """
    Return manifest levels as:
    [{index, label, target_field, parent_level, file}, ...]
    """
    code = _country_code_for(country)
    base = _country_base_path(code)
    if not os.path.isdir(base):
        frappe.throw(f"Country folder not found: {base}")

    m = _load_manifest(base)
    levels = m.get("levels", [])
    return [
        {
            "index": i + 1,
            "label": lvl["label"],
            "target_field": lvl["target_field"],
            "parent_level": lvl.get("parent_level"),
            "file": lvl["file"],
        }
        for i, lvl in enumerate(levels)
    ]


@frappe.whitelist(allow_guest=True)
def get_level_options(country: str, level_index: int, parent_code: str = None):
    """
    For level_index=1, CSV must have: code,name
    For level_index>=2, CSV must have: parent_code,code,name
    Returns: [{"label": name, "value": code}, ...]
    """
    code = _country_code_for(country)
    base = _country_base_path(code)
    if not os.path.isdir(base):
        frappe.throw(f"Country folder not found: {base}")

    manifest = _load_manifest(base)
    try:
        idx = int(level_index) - 1
        level = manifest["levels"][idx]
    except (ValueError, IndexError, KeyError):
        frappe.throw("Invalid level_index")

    csv_path = os.path.join(base, level["file"])
    rows = _read_csv(csv_path)

    # Validate headers strictly according to level
    if idx == 0:
        _ensure_headers(rows, ("code", "name"), csv_path)
        # No parent filter at level 1
        filtered = rows
    else:
        _ensure_headers(rows, ("parent_code", "code", "name"), csv_path)
        if not parent_code:
            return []
        filtered = [r for r in rows if (r.get("parent_code") or "") == parent_code]

    # Emit minimal payload
    return [{"label": r["name"], "value": r["code"]} for r in filtered]
