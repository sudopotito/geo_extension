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
        # Soft-fail: allow frontend to stay in freeform if code missing
        # You can switch this to `return country_name` if you prefer
        frappe.throw(f"No Country.code found for '{country_name}'")
    return code


def _country_base_path(code: str) -> str:
    return frappe.get_app_path(*_COUNTRIES_DIR, code)


def _load_manifest(base_path: str):
    """Return dict or None (soft-fail if manifest not found / invalid)."""
    mf = os.path.join(base_path, "manifest.json")
    if not os.path.exists(mf):
        return None
    try:
        with open(mf, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Corrupt/invalid JSON → treat as no manifest
        return None


def _read_csv(path: str):
    """Return list[dict] or [] (soft-fail if file missing)."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f, skipinitialspace=True))
    except Exception:
        return []


def _has_headers(rows, required: tuple[str, ...]) -> bool:
    if not rows:
        return False
    headers = {(k or "").strip() for k in rows[0].keys()}
    return all(h in headers for h in required)


# --- API ---


@frappe.whitelist(allow_guest=True)
def get_levels(country: str):
    """
    Return manifest levels as:
    [{index, label, target_field, parent_level, file}, ...]
    Soft-fail: return [] when not available.
    """
    try:
        code = _country_code_for(country)
        base = _country_base_path(code)
        if not os.path.isdir(base):
            return []
        m = _load_manifest(base)
        if not m:
            return []
        levels = m.get("levels", []) or []
        return [
            {
                "index": i + 1,
                "label": lvl["label"],
                "target_field": lvl["target_field"],
                "parent_level": lvl.get("parent_level"),
                "file": lvl.get("file"),
            }
            for i, lvl in enumerate(levels)
            if lvl.get("label") and lvl.get("target_field") and lvl.get("file")
        ]
    except Exception:
        # Any unexpected backend hiccup → guided mode unavailable
        return []


@frappe.whitelist(allow_guest=True)
def get_level_options(country: str, level_index: int, parent_code: str = None):
    """
    For level_index=1, CSV must have: code,name
    For level_index>=2, CSV must have: parent_code,code,name
    Returns: [{"label": name, "value": code}, ...]
    Soft-fail: return [] when not available / invalid.
    """
    try:
        code = _country_code_for(country)
        base = _country_base_path(code)
        if not os.path.isdir(base):
            return []

        manifest = _load_manifest(base)
        if not manifest:
            return []

        try:
            idx = int(level_index) - 1
            level = manifest["levels"][idx]
        except Exception:
            return []

        csv_path = os.path.join(base, level.get("file", ""))
        rows = _read_csv(csv_path)
        if idx == 0:
            # Expect code,name, but if headers are missing, soft-return []
            if not _has_headers(rows, ("code", "name")):
                return []
            filtered = rows
        else:
            if not _has_headers(rows, ("parent_code", "code", "name")):
                return []
            if not parent_code:
                return []
            filtered = [r for r in rows if (r.get("parent_code") or "") == parent_code]

        return [
            {"label": r.get("name", ""), "value": r.get("code", "")}
            for r in filtered
            if r.get("name") and r.get("code")
        ]
    except Exception:
        return []
