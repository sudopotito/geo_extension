# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

import csv
import json
import os
import re
import unicodedata

import frappe

_COUNTRIES_DIR = ("geo_extension", "setup", "data", "countries")

_MAX_TEXT_LEN = 512
_MAX_CODE_LEN = 128
_CODE_RE = re.compile(r"^[A-Za-z0-9._-]+$")


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


def _clean_text(value: str | None, max_len: int = _MAX_TEXT_LEN) -> str:
	"""
	Generic text sanitization:
	- strip whitespace
	- remove non-printable/control chars
	- remove <, >, and `
	- truncate to max_len
	"""
	s = (value or "").strip()
	if not s:
		return ""

	# Keep only printable characters
	s = "".join(ch for ch in s if ch.isprintable())

	# Strip obvious HTML/JS delimiters
	s = s.replace("<", "").replace(">", "").replace("`", "")

	if len(s) > max_len:
		s = s[:max_len]

	return s


def _clean_code(value: str | None) -> str:
	"""
	Codes are boring:
	- text-sanitized first
	- only [A-Za-z0-9._-]
	- bounded length
	"""
	s = _clean_text(value, max_len=_MAX_CODE_LEN)
	if not s:
		return ""
	if not _CODE_RE.fullmatch(s):
		return ""
	return s


def _safe_join(base: str, filename: str | None) -> str | None:
	"""
	Prevent path traversal via manifest 'file' value.
	Only allow relative paths that stay under `base`.
	"""
	filename = (filename or "").strip()
	if not filename:
		return None

	# Disallow absolute paths
	if os.path.isabs(filename):
		return None

	joined = os.path.normpath(os.path.join(base, filename))
	base_norm = os.path.normpath(base)

	# Joined path must remain inside base directory
	if not joined.startswith(base_norm + os.sep) and joined != base_norm:
		return None

	return joined


# ---------------- API ----------------


@frappe.whitelist(allow_guest=True)
def get_levels(country: str):
	"""
	Return a sanitized list of levels:
	[{index,label,target_field,parent_level,file}, ...]
	Soft-fail to [] on any issue.
	"""
	try:
		code = _country_code_for(country)
		base = _country_base_path(code)
		if not os.path.isdir(base):
			return []

		m = _load_manifest(base)
		if not m:
			return []

		raw_levels = m.get("levels", []) or []
		levels = []

		for i, lvl in enumerate(raw_levels):
			label = _clean_text(lvl.get("label"))
			target_field = _clean_text(lvl.get("target_field"), max_len=64)
			parent_level = lvl.get("parent_level")
			file_name = _clean_text(lvl.get("file"), max_len=128)

			if not label or not target_field or not file_name:
				# Skip incomplete or obviously bad entries
				continue

			if _safe_join(base, file_name) is None:
				# Path traversal or invalid path, skip this level
				continue

			levels.append(
				{
					"index": i + 1,
					"label": label,
					"target_field": target_field,
					"parent_level": parent_level,
					"file": file_name,
				}
			)

		return levels
	except Exception:
		return []


@frappe.whitelist(allow_guest=True)
def get_level_options(
	country: str,
	level_index: int,
	parent_code: str | None = None,
) -> list[dict[str, str]]:
	"""
	level_index=1: CSV requires code,name
	level_index>=2: CSV requires parent_code,code,name

	Returns sanitized:
	[{"label": name, "value": code}, ...] sorted A→Z by label.

	CSV-agnostic in spirit:
	- We don't assume anything about the content beyond the headers we read.
	- Everything we expose (code/name) is cleaned and bounded.
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

		csv_path = _safe_join(base, level.get("file"))
		if not csv_path:
			return []

		rows = _read_csv(csv_path)

		if idx == 0:
			# Top level: code,name
			if not _has_headers(rows, ("code", "name")):
				return []
			filtered = rows
			parent_code_clean = None
		else:
			# Sub-levels: parent_code,code,name
			if not _has_headers(rows, ("parent_code", "code", "name")):
				return []
			if not parent_code:
				return []

			parent_code_clean = _clean_code(parent_code)
			if not parent_code_clean:
				return []

			filtered = [r for r in rows if _eq(r.get("parent_code"), parent_code)]

		safe_rows = []
		for r in filtered:
			raw_name = r.get("name")
			raw_code = r.get("code")

			name = _clean_text(raw_name)
			code_val = _clean_code(raw_code)

			if not name or not code_val:
				continue

			# For sub-levels, re-check parent_code using cleaned code
			if idx > 0:
				raw_parent = r.get("parent_code")
				parent_val = _clean_code(raw_parent)
				if not parent_val or parent_val != parent_code_clean:
					continue

			safe_rows.append({"name": name, "code": code_val})

		# Sort A→Z on 'name' (label), Unicode-aware and case-insensitive
		safe_rows_sorted = sorted(
			safe_rows,
			key=lambda r: _sort_key(r.get("name", "")),
		)

		return [{"label": r["name"], "value": r["code"]} for r in safe_rows_sorted]
	except Exception:
		return []
