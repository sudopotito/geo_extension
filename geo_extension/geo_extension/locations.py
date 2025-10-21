import os, json, csv
import unicodedata  # <-- added
import frappe

_COUNTRIES_DIR = ("geo_extension", "setup", "data", "countries")

# ---------------- internals ----------------


def _country_code_for(country_name: str) -> str:
    if not country_name:
        frappe.throw("country is required")
    code = frappe.db.get_value("Country", country_name, "code")
    if not code:
        frappe.throw(f"No Country.code found for '{country_name}'")
    return code


def _country_base_path(code: str) -> str:
    """Case-insensitive lookup: try exact, lower, upper."""
    for c in (code, code.lower(), code.upper()):
        p = frappe.get_app_path(*_COUNTRIES_DIR, c)
        if os.path.isdir(p):
            return p
    # fallback (callers soft-fail)
    return frappe.get_app_path(*_COUNTRIES_DIR, code)


def _load_manifest(base_path: str):
    mf = os.path.join(base_path, "manifest.json")
    if not os.path.exists(mf):
        return None
    try:
        with open(mf, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _read_csv(path: str):
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


def _eq(a: str, b: str) -> bool:
    return (a or "").strip() == (b or "").strip()


def _sort_key(label: str) -> str:
    """
    Normalize accents and case-fold for stable A→Z sorting.
    Example: 'Ñuñoa' ~ 'Nunoa'
    """
    s = label or ""
    nfkd = unicodedata.normalize("NFKD", s)
    no_marks = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return no_marks.casefold()


# ---------------- API ----------------


@frappe.whitelist(allow_guest=True)
def get_levels(country: str):
    """Return [{index,label,target_field,parent_level,file}, ...] or [] on soft-fail."""
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
        return []


@frappe.whitelist(allow_guest=True)
def get_level_options(country: str, level_index: int, parent_code: str = None):
    """
    level_index=1: CSV requires code,name
    level_index>=2: CSV requires parent_code,code,name
    Returns: [{"label": name, "value": code}, ...] sorted A→Z by label.
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
            if not _has_headers(rows, ("code", "name")):
                return []
            filtered = rows
        else:
            if not _has_headers(rows, ("parent_code", "code", "name")):
                return []
            if not parent_code:
                return []
            filtered = [r for r in rows if _eq(r.get("parent_code"), parent_code)]

        # Sort A→Z on 'name' (label), Unicode-aware and case-insensitive
        filtered_sorted = sorted(
            (r for r in filtered if r.get("name") and r.get("code")),
            key=lambda r: _sort_key(r.get("name", "")),
        )

        return [
            {"label": r.get("name", ""), "value": r.get("code", "")}
            for r in filtered_sorted
        ]
    except Exception:
        return []
