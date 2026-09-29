# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Geographic dataset loading and indexing.

A *country dataset* is a directory that contains a ``manifest.json`` and one
CSV file per administrative level (optionally plus a ``postal_codes.csv``).
See ``template/README.md`` for the contributor-facing description of the
format.

The engine only knows generic concepts:

- **level**: one administrative tier (1 = top). Each level maps to one native
  Address field (``target_field``) and has a human label.
- **unit**: one geographic record identified by ``(level, code)``. Codes are
  the stable identifiers; names are for display only.
- **parent / children**: every unit below level 1 references a unit of the
  previous level through ``parent_code``.
- **postal codes**: optional ``(level, code) -> [postal_code, ...]`` lookups.

This module has no Frappe dependency so it can be used by the validator,
tests and CI without a site.
"""

from __future__ import annotations

import csv
import json
import os
import re
import threading
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

#: Native Address fields a level may populate.
ALLOWED_TARGET_FIELDS = ("state", "county", "city", "address_line2")

#: Native Address field postal codes populate.
POSTAL_TARGET_FIELD = "pincode"

#: Hard limits (kept generous for official government datasets).
MAX_LEVELS = 6
MAX_TEXT_LEN = 512
MAX_CODE_LEN = 128
MAX_POSTAL_LEN = 32

CODE_RE = re.compile(r"^[A-Za-z0-9._-]+$")
COUNTRY_CODE_RE = re.compile(r"^[a-z]{2}$")

MANIFEST_FILE = "manifest.json"
POSTAL_KEY = "postal_codes"

LEVEL1_HEADERS = ("code", "name")
LEVELN_HEADERS = ("parent_code", "code", "name")
POSTAL_HEADERS = ("level", "code", "postal_code")

#: Optional column on every level file: alternative spellings, ``|``-separated.
ALIASES_COLUMN = "aliases"
ALIAS_SEP = "|"
MAX_ALIASES = 20
MAX_SEARCH_RESULTS = 50

#: Directory that ships with the app.
BUILTIN_ROOT = os.path.join(
	os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "setup", "data", "countries"
)


class DatasetError(Exception):
	"""Raised when a dataset is structurally unusable (missing/broken manifest)."""


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------


def clean_text(value: str | None, max_len: int = MAX_TEXT_LEN) -> str:
	"""Strip whitespace and control characters, drop HTML delimiters, bound length."""
	s = re.sub(r"\s+", " ", value or "").strip()
	if not s:
		return ""
	s = "".join(ch for ch in s if ch.isprintable())
	s = s.replace("<", "").replace(">", "").replace("`", "").strip()
	return s[:max_len]


def clean_code(value: str | None) -> str:
	"""Codes may only contain ``[A-Za-z0-9._-]``; anything else is rejected."""
	s = clean_text(value, max_len=MAX_CODE_LEN)
	if not s or not CODE_RE.fullmatch(s):
		return ""
	return s


def normalize_name(value: str | None) -> str:
	"""Accent- and case-insensitive key used for matching and sorting ('Ñuñoa' ~ 'nunoa')."""
	nfkd = unicodedata.normalize("NFKD", value or "")
	no_marks = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
	return re.sub(r"\s+", " ", no_marks).strip().casefold()


def normalize_country_code(value: str | None) -> str:
	code = (value or "").strip().lower()
	return code if COUNTRY_CODE_RE.fullmatch(code) else ""


# ---------------------------------------------------------------------------
# low level readers (shared with the validator)
# ---------------------------------------------------------------------------


def safe_join(base: str, filename: str | None) -> str | None:
	"""Join ``filename`` under ``base`` and refuse anything that escapes ``base``."""
	filename = (filename or "").strip()
	if not filename or os.path.isabs(filename):
		return None
	joined = os.path.normpath(os.path.join(base, filename))
	base_norm = os.path.normpath(base)
	if joined != base_norm and not joined.startswith(base_norm + os.sep):
		return None
	return joined


def read_manifest(path: str) -> dict:
	"""Read and JSON-decode ``manifest.json`` in ``path``. Raises DatasetError."""
	mf = os.path.join(path, MANIFEST_FILE)
	if not os.path.isfile(mf):
		raise DatasetError(f"{MANIFEST_FILE} not found in {path}")
	try:
		with open(mf, encoding="utf-8") as f:
			data = json.load(f)
	except (OSError, ValueError) as e:
		raise DatasetError(f"{mf}: {e}") from e
	if not isinstance(data, dict):
		raise DatasetError(f"{mf}: manifest must be a JSON object")
	return data


def read_csv_rows(path: str) -> tuple[list[str], list[dict[str, str]]]:
	"""
	Return ``(headers, rows)``. Headers are stripped; a UTF-8 BOM is tolerated.
	Raises DatasetError when the file cannot be read.
	"""
	try:
		with open(path, newline="", encoding="utf-8-sig") as f:
			reader = csv.DictReader(f, skipinitialspace=True)
			headers = [(h or "").strip() for h in (reader.fieldnames or [])]
			rows = []
			for raw in reader:
				rows.append({(k or "").strip(): (v or "").strip() for k, v in raw.items() if k is not None})
			return headers, rows
	except (OSError, UnicodeDecodeError, csv.Error) as e:
		raise DatasetError(f"{path}: {e}") from e


# ---------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Level:
	index: int  # 1-based
	label: str
	target_field: str
	file: str

	def as_dict(self) -> dict:
		return {"level": self.index, "label": self.label, "target_field": self.target_field}


@dataclass(frozen=True)
class Unit:
	level: int
	code: str
	name: str
	parent: str | None = None
	aliases: tuple[str, ...] = ()
	#: normalized name and aliases, precomputed for matching
	keys: tuple[str, ...] = ()

	def as_option(self) -> dict:
		option = {"value": self.code, "label": self.name}
		if self.aliases:
			option["aliases"] = list(self.aliases)
		return option

	def matches(self, key: str) -> bool:
		"""Exact match of a normalized string against the name or any alias."""
		return bool(key) and key in self.keys


def make_unit(level: int, code: str, name: str, parent: str | None = None, aliases=()) -> Unit:
	name_key = normalize_name(name)
	clean_aliases: list[str] = []
	keys = [name_key]
	for alias in aliases:
		key = normalize_name(alias)
		if key and key not in keys:
			clean_aliases.append(alias)
			keys.append(key)
	return Unit(
		level=level, code=code, name=name, parent=parent, aliases=tuple(clean_aliases), keys=tuple(keys)
	)


def parse_aliases(value: str | None) -> list[str]:
	out: list[str] = []
	for raw in (value or "").split(ALIAS_SEP):
		alias = clean_text(raw, 140)
		if alias and alias not in out:
			out.append(alias)
	return out[:MAX_ALIASES]


@dataclass
class CountryDataset:
	code: str
	path: str
	manifest: dict
	levels: list[Level]
	units: list[dict[str, Unit]] = field(default_factory=list)  # per level: code -> Unit
	children: list[dict[str | None, list[Unit]]] = field(default_factory=list)  # per level: parent -> [Unit]
	postal: dict[tuple[int, str], list[str]] = field(default_factory=dict)
	postal_pattern: re.Pattern | None = None
	has_postal_file: bool = False
	warnings: list[str] = field(default_factory=list)

	def __repr__(self) -> str:
		return f"CountryDataset(code={self.code!r}, levels={len(self.levels)}, counts={self.counts()})"

	# -- hierarchy -------------------------------------------------------

	@property
	def depth(self) -> int:
		return len(self.levels)

	def get_level(self, index: int) -> Level | None:
		if 1 <= index <= len(self.levels):
			return self.levels[index - 1]
		return None

	def get_unit(self, level: int, code: str) -> Unit | None:
		if not (1 <= level <= len(self.levels)):
			return None
		return self.units[level - 1].get(code)

	def get_parent(self, unit: Unit) -> Unit | None:
		if unit.level <= 1 or unit.parent is None:
			return None
		return self.get_unit(unit.level - 1, unit.parent)

	def ancestors(self, unit: Unit) -> list[Unit]:
		"""Return ``[unit, parent, grandparent, ...]``."""
		chain = [unit]
		cur = self.get_parent(unit)
		while cur is not None:
			chain.append(cur)
			cur = self.get_parent(cur)
		return chain

	def options(
		self,
		level: int,
		parent: str | None = None,
		txt: str | None = None,
		limit: int | None = None,
	) -> list[Unit]:
		"""
		Children of ``parent`` at ``level`` (roots when level == 1), sorted A→Z.
		``txt`` filters by accent/case-insensitive substring.
		"""
		if not (1 <= level <= len(self.levels)):
			return []
		if level == 1:
			rows = self.children[0].get(None, [])
		else:
			if not parent:
				return []
			rows = self.children[level - 1].get(parent, [])
		if txt:
			needle = normalize_name(txt)
			rows = [u for u in rows if needle in normalize_name(u.name)]
		if limit is not None and limit >= 0:
			rows = rows[:limit]
		return list(rows)

	def find_by_name(self, level: int, name: str, parent: str | None = None) -> Unit | None:
		"""
		Exact (accent/case-insensitive) match of ``name`` against the names and aliases
		of the candidates at ``level``. A name match wins over an alias match.
		"""
		key = normalize_name(name)
		if not key:
			return None
		candidates = self.options(level, parent)
		for unit in candidates:
			if unit.keys and unit.keys[0] == key:
				return unit
		for unit in candidates:
			if unit.matches(key):
				return unit
		return None

	def get_path(self, unit: Unit) -> list[Unit]:
		"""Return ``[top, ..., parent, unit]``."""
		return list(reversed(self.ancestors(unit)))

	def search(self, txt: str, limit: int = MAX_SEARCH_RESULTS, level: int | None = None) -> list[Unit]:
		"""
		Substring search across every level (or one ``level``) by name or alias.
		Results whose name starts with the text come first, then by level and name.
		"""
		needle = normalize_name(txt)
		if not needle:
			return []
		levels = [level] if level else range(1, len(self.levels) + 1)
		scored: list[tuple[int, int, str, Unit]] = []
		for lvl in levels:
			if not (1 <= lvl <= len(self.levels)):
				continue
			for unit in self.units[lvl - 1].values():
				rank = None
				for key in unit.keys:
					if key.startswith(needle):
						rank = 0
						break
					if needle in key:
						rank = 1
				if rank is not None:
					scored.append((rank, unit.level, unit.keys[0], unit))
		scored.sort(key=lambda t: t[:3])
		return [t[3] for t in scored[: max(limit, 0)]]

	def resolve(self, names: list[str | None]) -> list[Unit]:
		"""
		Resolve an ordered list of names (one per level, top first) into units.
		Stops at the first level that cannot be matched.
		"""
		chain: list[Unit] = []
		parent: str | None = None
		for i, name in enumerate(names[: len(self.levels)]):
			if not name:
				break
			unit = self.find_by_name(i + 1, name, parent)
			if unit is None:
				break
			chain.append(unit)
			parent = unit.code
		return chain

	# -- postal codes ------------------------------------------------------

	@property
	def has_postal_codes(self) -> bool:
		return bool(self.postal)

	def postal_codes_for(self, level: int, code: str) -> tuple[list[str], int | None]:
		"""
		Postal codes for the unit, falling back to its ancestors.
		Returns ``(codes, level_that_provided_them)``; ``([], None)`` when unknown.
		"""
		unit = self.get_unit(level, code)
		if unit is None:
			return [], None
		for u in self.ancestors(unit):
			codes = self.postal.get((u.level, u.code))
			if codes:
				return list(codes), u.level
		return [], None

	# -- summary ----------------------------------------------------------

	def counts(self) -> list[int]:
		return [len(u) for u in self.units]

	def info(self) -> dict:
		m = self.manifest
		return {
			"country_code": self.code,
			"name": clean_text(m.get("name")),
			"version": clean_text(m.get("version"), 32),
			"description": clean_text(m.get("description")),
			"source": clean_text(m.get("source")),
			"license": clean_text(m.get("license")),
			"levels": [lvl.as_dict() for lvl in self.levels],
			"counts": self.counts(),
			"postal_codes": self.has_postal_codes,
		}


# ---------------------------------------------------------------------------
# manifest parsing
# ---------------------------------------------------------------------------


def parse_levels(manifest: dict) -> list[Level]:
	"""
	Build the level list from a manifest, silently skipping unusable entries.
	The validator reports the same problems loudly.
	"""
	raw = manifest.get("levels")
	if not isinstance(raw, list):
		return []
	levels: list[Level] = []
	seen_fields: set[str] = set()
	for entry in raw[:MAX_LEVELS]:
		if not isinstance(entry, dict):
			continue
		label = clean_text(entry.get("label"), 140)
		target_field = clean_text(entry.get("target_field"), 64)
		file_name = clean_text(entry.get("file"), 128)
		if not (label and file_name and target_field in ALLOWED_TARGET_FIELDS):
			continue
		if target_field in seen_fields:
			continue
		seen_fields.add(target_field)
		levels.append(Level(index=len(levels) + 1, label=label, target_field=target_field, file=file_name))
	return levels


def parse_postal_config(manifest: dict) -> tuple[str | None, re.Pattern | None]:
	"""Return ``(file_name, compiled_pattern)`` from ``manifest["postal_codes"]``."""
	cfg = manifest.get(POSTAL_KEY)
	if not isinstance(cfg, dict):
		return None, None
	file_name = clean_text(cfg.get("file"), 128) or None
	pattern = None
	raw_pattern = cfg.get("pattern")
	if isinstance(raw_pattern, str) and raw_pattern.strip():
		try:
			pattern = re.compile(raw_pattern)
		except re.error:
			pattern = None
	return file_name, pattern


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------


def _load_level_units(ds: CountryDataset, level: Level) -> None:
	idx = level.index - 1
	ds.units.append({})
	ds.children.append({})

	path = safe_join(ds.path, level.file)
	if not path or not os.path.isfile(path):
		ds.warnings.append(f"level {level.index}: file '{level.file}' not found")
		return

	try:
		headers, rows = read_csv_rows(path)
	except DatasetError as e:
		ds.warnings.append(f"level {level.index}: {e}")
		return

	required = LEVEL1_HEADERS if idx == 0 else LEVELN_HEADERS
	if any(h not in headers for h in required):
		ds.warnings.append(f"level {level.index}: missing required columns {required}")
		return

	by_code = ds.units[idx]
	children = ds.children[idx]
	parents = ds.units[idx - 1] if idx > 0 else None
	skipped = 0

	for row in rows:
		code = clean_code(row.get("code"))
		name = clean_text(row.get("name"))
		parent = clean_code(row.get("parent_code")) if idx > 0 else None
		if not code or not name or (idx > 0 and not parent):
			skipped += 1
			continue
		if code in by_code:
			skipped += 1
			continue
		if idx > 0 and parent not in parents:
			skipped += 1
			continue
		unit = make_unit(level.index, code, name, parent, parse_aliases(row.get(ALIASES_COLUMN)))
		by_code[code] = unit
		children.setdefault(parent, []).append(unit)

	if skipped:
		ds.warnings.append(f"level {level.index}: skipped {skipped} unusable row(s)")

	for key, units in children.items():
		units.sort(key=lambda u: (normalize_name(u.name), u.code))
		children[key] = units


def _load_postal_codes(ds: CountryDataset, file_name: str | None) -> None:
	if not file_name:
		return
	ds.has_postal_file = True
	path = safe_join(ds.path, file_name)
	if not path or not os.path.isfile(path):
		ds.warnings.append(f"postal codes: file '{file_name}' not found")
		return
	try:
		headers, rows = read_csv_rows(path)
	except DatasetError as e:
		ds.warnings.append(f"postal codes: {e}")
		return
	if any(h not in headers for h in POSTAL_HEADERS):
		ds.warnings.append(f"postal codes: missing required columns {POSTAL_HEADERS}")
		return

	skipped = 0
	for row in rows:
		try:
			level = int(row.get("level") or 0)
		except ValueError:
			level = 0
		code = clean_code(row.get("code"))
		postal = clean_text(row.get("postal_code"), MAX_POSTAL_LEN)
		if not (code and postal and ds.get_unit(level, code)):
			skipped += 1
			continue
		if ds.postal_pattern and not ds.postal_pattern.fullmatch(postal):
			skipped += 1
			continue
		bucket = ds.postal.setdefault((level, code), [])
		if postal not in bucket:
			bucket.append(postal)

	for bucket in ds.postal.values():
		bucket.sort()
	if skipped:
		ds.warnings.append(f"postal codes: skipped {skipped} unusable row(s)")


def load_dataset(path: str, code: str | None = None) -> CountryDataset:
	"""
	Load and index the dataset directory at ``path``.
	Raises DatasetError when the manifest is missing/broken or defines no usable level.
	"""
	if not os.path.isdir(path):
		raise DatasetError(f"dataset directory not found: {path}")
	manifest = read_manifest(path)
	levels = parse_levels(manifest)
	if not levels:
		raise DatasetError(f"{path}: manifest defines no usable levels")

	code = normalize_country_code(code or manifest.get("country_code") or os.path.basename(path))
	ds = CountryDataset(code=code, path=path, manifest=manifest, levels=levels)

	for level in levels:
		_load_level_units(ds, level)

	postal_file, pattern = parse_postal_config(manifest)
	ds.postal_pattern = pattern
	_load_postal_codes(ds, postal_file)
	return ds


# ---------------------------------------------------------------------------
# discovery + cache
# ---------------------------------------------------------------------------


def dataset_roots(extra_roots: list[str] | None = None) -> list[str]:
	"""Directories searched for ``<country_code>/manifest.json`` (first match wins)."""
	roots: list[str] = []
	for r in extra_roots or []:
		if r and r not in roots:
			roots.append(r)
	roots.append(BUILTIN_ROOT)
	return roots


def find_country_path(code: str, extra_roots: list[str] | None = None) -> str | None:
	code = normalize_country_code(code)
	if not code:
		return None
	for root in dataset_roots(extra_roots):
		p = os.path.join(root, code)
		if os.path.isfile(os.path.join(p, MANIFEST_FILE)):
			return p
	return None


def list_country_codes(extra_roots: list[str] | None = None) -> list[str]:
	codes: set[str] = set()
	for root in dataset_roots(extra_roots):
		if not os.path.isdir(root):
			continue
		for entry in os.scandir(root):
			if entry.is_dir() and normalize_country_code(entry.name):
				if os.path.isfile(os.path.join(entry.path, MANIFEST_FILE)):
					codes.add(entry.name.lower())
	return sorted(codes)


def _dir_stamp(path: str) -> tuple:
	"""Cheap change detector: names, sizes and mtimes of the files in the directory."""
	stamp = []
	try:
		for entry in sorted(os.scandir(path), key=lambda e: e.name):
			if entry.is_file():
				st = entry.stat()
				stamp.append((entry.name, st.st_size, st.st_mtime_ns))
	except OSError:
		pass
	return tuple(stamp)


_cache: dict[str, tuple[tuple, CountryDataset]] = {}
_cache_lock = threading.Lock()


def get_dataset(code: str, extra_roots: list[str] | None = None) -> CountryDataset | None:
	"""
	Return the indexed dataset for ``code`` (ISO alpha-2, case-insensitive) or ``None``
	when no dataset exists. Parsed datasets are cached per process and reloaded
	automatically when any file in the directory changes.

	Raises DatasetError when the directory exists but is unusable.
	"""
	path = find_country_path(code, extra_roots)
	if not path:
		return None
	stamp = _dir_stamp(path)
	with _cache_lock:
		cached = _cache.get(path)
		if cached and cached[0] == stamp:
			return cached[1]
	ds = load_dataset(path)
	with _cache_lock:
		_cache[path] = (stamp, ds)
	return ds


def clear_cache() -> None:
	with _cache_lock:
		_cache.clear()
