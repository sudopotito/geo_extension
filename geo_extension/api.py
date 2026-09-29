# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Public geographic API.

These endpoints are the only thing the Address form (or any other consumer:
web forms, portal pages, other apps) talks to. They are country-agnostic and
never fail hard: an unsupported country, a missing dataset or a broken file
simply yields "no data" so native Address entry keeps working.

Geographic data is public information, so the endpoints allow guest access
(needed by website checkout/registration forms).

	get_hierarchy(country)                      -> levels + field mapping
	get_options(country, level, parent, txt)    -> children of a unit
	resolve(country, names)                     -> names -> stable codes
	get_postal_codes(country, level, code)      -> postal codes for a unit
	search(country, txt, level, limit)          -> units matching text, with their path
"""

from __future__ import annotations

import json

import frappe
from frappe.utils import cint

from geo_extension.geo import dataset as ds

MAX_OPTIONS = 5000


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _extra_roots() -> list[str] | None:
	"""Site-specific dataset directories (``geo_extension_dataset_roots`` in site config)."""
	roots = frappe.flags.get("geo_extension_dataset_roots") or frappe.conf.get("geo_extension_dataset_roots")
	if isinstance(roots, str):
		roots = [roots]
	return list(roots) if roots else None


def get_country_code(country: str | None) -> str | None:
	"""Accept a Country name (``Philippines``) or an ISO alpha-2 code (``ph``)."""
	value = (country or "").strip()
	if not value:
		return None
	code = ds.normalize_country_code(value)
	if code:
		return code
	if not frappe.db.exists("Country", value):
		return None
	return ds.normalize_country_code(frappe.get_cached_value("Country", value, "code")) or None


def get_dataset(country: str | None) -> ds.CountryDataset | None:
	"""Indexed dataset for a country name/code, or ``None`` when unsupported or broken."""
	code = get_country_code(country)
	if not code:
		return None
	try:
		return ds.get_dataset(code, _extra_roots())
	except ds.DatasetError as e:
		frappe.logger("geo_extension").warning(f"dataset for '{code}' is unusable: {e}")
		return None


def _parse_names(names) -> list[str | None]:
	if isinstance(names, str):
		try:
			names = json.loads(names)
		except ValueError:
			return []
	if isinstance(names, dict):
		# {"1": "Cebu", "2": "Cebu City"} or {"state": ...} are both tolerated
		out: list[str | None] = []
		for key in sorted(names, key=lambda k: cint(k) if str(k).isdigit() else 0):
			out.append(names[key])
		names = out
	if not isinstance(names, list):
		return []
	return [ds.clean_text(n) if isinstance(n, str) else None for n in names]


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_hierarchy(country: str | None = None) -> dict:
	"""
	Describe how a country's administrative hierarchy maps onto native Address fields.

	Returns ``{"supported": False}`` for countries without a dataset, otherwise::

	    {
	        "supported": True,
	        "country_code": "ph",
	        "levels": [
	            {"level": 1, "label": "Province", "target_field": "state"},
	            {"level": 2, "label": "City/Municipality", "target_field": "city"},
	            {"level": 3, "label": "Barangay", "target_field": "county"},
	        ],
	        "postal_codes": {"available": false, "target_field": "pincode"},
	    }
	"""
	dataset = get_dataset(country)
	if dataset is None:
		return {"supported": False, "levels": [], "postal_codes": {"available": False}}
	return {
		"supported": True,
		"country_code": dataset.code,
		"levels": [lvl.as_dict() for lvl in dataset.levels],
		"postal_codes": {
			"available": dataset.has_postal_codes,
			"target_field": ds.POSTAL_TARGET_FIELD,
		},
	}


@frappe.whitelist(allow_guest=True)
def get_options(
	country: str | None = None,
	level: int | str = 1,
	parent: str | None = None,
	txt: str | None = None,
	limit: int | str | None = None,
	parent_level: int | str | None = None,
) -> list[dict]:
	"""
	Units at ``level`` below ``parent`` as ``[{"value": code, "label": name}, ...]``,
	sorted A→Z. ``level`` is 1-based; level 1 ignores ``parent``. Levels above 1
	require ``parent`` so the browser never receives a whole country at once.
	``parent`` may be any ancestor (a state code for level 3) for forms that have
	no field for the level in between; pass ``parent_level`` to say which level
	the code belongs to.
	"""
	dataset = get_dataset(country)
	if dataset is None:
		return []
	level = cint(level)
	parent_code = ds.clean_code(parent) if parent else None
	if level > 1 and not parent_code:
		return []
	txt = ds.clean_text(txt, 140) if txt else None
	limit = cint(limit) if limit else MAX_OPTIONS
	limit = min(max(limit, 1), MAX_OPTIONS)
	parent_level = cint(parent_level) or None
	return [u.as_option() for u in dataset.options(level, parent_code, txt, limit, parent_level)]


@frappe.whitelist(allow_guest=True)
def resolve(country: str | None = None, names=None, levels=None) -> list[dict]:
	"""
	Turn already-entered names into stable codes, top level first.

	``names`` is a JSON list ordered by level (``["Cebu", "Cebu City", "Lahug"]``);
	``levels`` optionally gives each name's level (``[1, 3]`` when the form has no
	field for level 2). Matching is exact but accent/case-insensitive and stops at
	the first name that does not match, so manually entered values simply end the
	chain. Returns ``[{"level": 1, "value": "022", "label": "Cebu"}, ...]``.
	"""
	dataset = get_dataset(country)
	if dataset is None:
		return []
	names = _parse_names(names)
	level_list = _parse_levels(levels, len(names))
	chain = dataset.resolve(names, level_list)
	return [{"level": u.level, **u.as_option()} for u in chain]


def _parse_levels(value, count: int) -> list[int] | None:
	"""``[1, 3]`` (JSON or list) -> ints; ``None`` when absent or unusable."""
	if value is None or value == "":
		return None
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			return None
	if not isinstance(value, list) or len(value) != count:
		return None
	try:
		levels = [int(v) for v in value]
	except (TypeError, ValueError):
		return None
	return levels if all(1 <= v <= ds.MAX_LEVELS for v in levels) else None


@frappe.whitelist(allow_guest=True)
def get_postal_codes(country: str | None = None, level: int | str = 1, code: str | None = None) -> dict:
	"""
	Postal codes for a unit, falling back to its ancestors when the unit itself
	has none (e.g. barangay -> city). Returns ``{"codes": [...], "level": n}``;
	``codes`` is empty when nothing reliable is known. Never guesses.
	"""
	dataset = get_dataset(country)
	code_clean = ds.clean_code(code) if code else ""
	if dataset is None or not code_clean:
		return {"codes": [], "level": None}
	codes, found_level = dataset.postal_codes_for(cint(level), code_clean)
	return {"codes": codes, "level": found_level}


@frappe.whitelist(allow_guest=True)
def search(
	country: str | None = None,
	txt: str | None = None,
	level: int | str | None = None,
	limit: int | str | None = None,
) -> list[dict]:
	"""
	Find units at any level (or one ``level``) whose name or alias contains ``txt``.
	Each hit carries its full ``path`` (top level first, ending with the hit itself),
	so a single search box can fill every level of a form at once::

	    [
	        {
	            "level": 2,
	            "value": "1380100000",
	            "label": "City of Caloocan",
	            "path": [
	                {"level": 1, "value": "1300000000", "label": "Metro Manila"},
	                {"level": 2, "value": "1380100000", "label": "City of Caloocan"},
	            ],
	        }
	    ]
	"""
	dataset = get_dataset(country)
	txt = ds.clean_text(txt, 140) if txt else ""
	if dataset is None or len(txt) < 2:
		return []
	limit = min(max(cint(limit) or ds.MAX_SEARCH_RESULTS, 1), ds.MAX_SEARCH_RESULTS)
	level_int = cint(level) or None
	out = []
	for unit in dataset.search(txt, limit, level_int):
		out.append(
			{
				"level": unit.level,
				**unit.as_option(),
				"path": [{"level": u.level, **u.as_option()} for u in dataset.get_path(unit)],
			}
		)
	return out


@frappe.whitelist()
def get_supported_countries() -> list[dict]:
	"""Metadata of every installed dataset (name, levels, counts, source, license)."""
	out = []
	for code in ds.list_country_codes(_extra_roots()):
		try:
			dataset = ds.get_dataset(code, _extra_roots())
		except ds.DatasetError:
			continue
		if dataset is not None:
			out.append(dataset.info())
	return out
