#!/usr/bin/env python3
# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Generate a geo_extension country dataset from GeoNames (https://www.geonames.org, CC BY 4.0).

This is a maintainer tool. It is not installed with the app and has no Frappe
dependency. Usage::

    python tools/geonames/build_dataset.py us --work /tmp/geonames --out geo_extension/setup/data/countries

It downloads (or reuses) ``dump/<CC>.zip`` and ``zip/<CC>.zip`` from
download.geonames.org, then writes ``manifest.json``, ``level*.csv`` and, when
postal data is usable, ``postal_codes.csv`` according to ``countries.json``.

Per-country configuration (``countries.json``)::

    "us": {
      "name": "United States",
      "levels": [
        {"source": "ADM1", "label": "State",  "target_field": "state"},
        {"source": "ADM2", "label": "County", "target_field": "county"},
        {"source": "P",    "label": "City",   "target_field": "city"}
      ],
      "places": {"min_population": 500, "feature_codes": ["PPL", "PPLA", ...]},
      "postal_codes": {"enabled": true, "pattern": "^[0-9]{5}$", "attach_to": ["P", "ADM2"]}
    }

- ``source`` is a GeoNames feature code for administrative units (ADM1..ADM5)
  or ``P`` for populated places. Levels must be listed top-down.
- ``strip`` (optional, per level) lists regular expressions removed from the
  display name (``"^Changwat "``, ``" İlçesi$"``); the original name becomes
  an alias so it still matches when typed.
- ``names`` (optional, per country) maps a GeoNames id to the display name to
  use instead of the gazetteer's (for example the customary English name of an
  Egyptian governorate); the original name becomes an alias.
- Codes are GeoNames ids (stable across GeoNames updates).
- ``aliases`` gets the ASCII name when it differs from the display name.
- Postal codes are attached to the deepest unit that can be identified: a
  place matched by name inside the right administrative unit, otherwise the
  administrative unit itself, following ``attach_to`` in order. When the
  postal row carries no usable admin codes, a place or unit whose name is
  unique nationwide is accepted. Rows that match nothing are dropped:
  nothing is guessed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import unicodedata
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date

BASE_URL = "https://download.geonames.org/export"
HERE = os.path.dirname(os.path.abspath(__file__))

DEFAULT_PLACE_CODES = ["PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLCH", "PPLG", "PPLS"]
SEAT_CODES = {"PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLA5", "PPLC", "PPLG"}

# GeoNames "geoname" table columns
GID, NAME, ASCII, ALT, LAT, LNG, FCLASS, FCODE, CC, CC2, A1, A2, A3, A4, POP = range(15)


def norm(text: str) -> str:
	nfkd = unicodedata.normalize("NFKD", text or "")
	s = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
	return re.sub(r"\s+", " ", s).strip().casefold().replace("\u0131", "i")


def download(url: str, dest: str) -> str:
	if os.path.exists(dest) and os.path.getsize(dest) > 0:
		return dest
	os.makedirs(os.path.dirname(dest), exist_ok=True)
	print(f"downloading {url}")
	with urllib.request.urlopen(url, timeout=600) as r, open(dest, "wb") as f:
		while True:
			chunk = r.read(1 << 20)
			if not chunk:
				break
			f.write(chunk)
	return dest


def read_zip_tsv(path: str, member: str) -> list[list[str]]:
	with zipfile.ZipFile(path) as z, z.open(member) as f:
		text = io.TextIOWrapper(f, encoding="utf-8", newline="")
		return list(csv.reader(text, delimiter="\t", quoting=csv.QUOTE_NONE))


class Builder:
	def __init__(self, cc: str, config: dict, work: str):
		self.cc = cc.lower()
		self.CC = cc.upper()
		self.config = config
		self.work = work
		self.rows: list[list[str]] = []
		# admin units keyed by (feature code, admin code path)
		self.admin: dict[str, dict[tuple[str, ...], list[str]]] = defaultdict(dict)
		self.level_units: list[dict[str, dict]] = []  # per level: code -> unit dict
		self.warnings: list[str] = []

	# -- loading ----------------------------------------------------------

	def load(self) -> None:
		dump = download(f"{BASE_URL}/dump/{self.CC}.zip", os.path.join(self.work, "dump", f"{self.CC}.zip"))
		self.rows = [r for r in read_zip_tsv(dump, f"{self.CC}.txt") if len(r) >= 15]
		for r in self.rows:
			if r[FCLASS] == "A" and r[FCODE].startswith("ADM") and r[FCODE] != "ADMD":
				depth = {"ADM1": 1, "ADM2": 2, "ADM3": 3, "ADM4": 4, "ADM5": 5}.get(r[FCODE])
				if not depth:
					continue
				path = tuple(r[A1 : A1 + depth])
				if all(path):
					self.admin[r[FCODE]].setdefault(path, r)

	# -- hierarchy --------------------------------------------------------

	@staticmethod
	def _depth(source: str) -> int:
		return int(source[3:]) if source.startswith("ADM") else 99

	def build_levels(self) -> None:
		levels = self.config["levels"]
		places_cfg = self.config.get("places", {})
		min_pop = int(places_cfg.get("min_population", 500))
		codes_ok = set(places_cfg.get("feature_codes", DEFAULT_PLACE_CODES))
		keep_seats = bool(places_cfg.get("keep_seats", True))
		max_place_depth = None

		parent_paths: dict[tuple[str, ...], str] = {}  # admin path -> code of unit at previous level
		for i, lvl in enumerate(levels):
			source = lvl["source"]
			units: dict[str, dict] = {}
			self.level_units.append(units)
			if source.startswith("ADM"):
				depth = self._depth(source)
				max_place_depth = depth
				for path, r in self.admin[source].items():
					parent_code = None
					if i > 0:
						parent_code = self._find_parent(path, levels[:i], parent_paths)
						if parent_code is None:
							continue
					units[r[GID]] = self._unit(r, parent_code, lvl.get("strip"))
				parent_paths = {path: r[GID] for path, r in self.admin[source].items() if r[GID] in units}
			elif source == "P":
				by_key: dict[tuple, list[str]] = {}
				for r in self.rows:
					if r[FCLASS] != "P" or r[FCODE] not in codes_ok:
						continue
					pop = int(r[POP] or 0)
					if pop < min_pop and not (keep_seats and r[FCODE] in SEAT_CODES):
						continue
					parent_code = None
					if i > 0:
						parent_code = self._find_parent(
							tuple(r[A1 : A1 + (max_place_depth or 1)]), levels[:i], parent_paths
						)
						if parent_code is None:
							continue
					key = (parent_code, norm(r[NAME]))
					existing = by_key.get(key)
					if existing and int(existing[POP] or 0) >= pop:
						continue
					by_key[key] = r
					units[r[GID]] = self._unit(r, parent_code, lvl.get("strip"))
				# drop lower-population duplicates that were replaced
				keep = {r[GID] for r in by_key.values()}
				for gid in list(units):
					if gid not in keep:
						del units[gid]
			else:
				raise SystemExit(f"unknown level source {source!r}")
			print(f"  level {i + 1} {lvl['label']}: {len(units)} units")

	def _find_parent(self, path: tuple[str, ...], upper_levels: list[dict], parent_paths: dict) -> str | None:
		"""Code of the unit at the previous level that contains ``path``."""
		prev = upper_levels[-1]["source"]
		depth = self._depth(prev)
		key = tuple(path[:depth])
		if len(key) < depth or not all(key):
			return None
		return parent_paths.get(key)

	def _unit(self, r: list[str], parent: str | None, strip: list[str] | None = None) -> dict:
		aliases = []
		original = re.sub(r"\s+", " ", r[NAME]).strip()
		name = self.config.get("names", {}).get(r[GID]) or original
		for pattern in strip or []:
			name = re.sub(pattern, "", name).strip()
		if not name:
			name = original
		if norm(name) != norm(original):
			aliases.append(original)
		if r[ASCII] and norm(r[ASCII]) not in {norm(name), norm(original)}:
			aliases.append(r[ASCII])
		return {
			"code": r[GID],
			"name": name,
			"parent": parent,
			"aliases": aliases,
			"path": tuple(r[A1 : A4 + 1]),
			"pop": int(r[POP] or 0),
		}

	# -- postal codes -------------------------------------------------------

	def build_postal(self) -> list[tuple[int, str, str]]:
		cfg = self.config.get("postal_codes") or {}
		if not cfg.get("enabled"):
			return []
		zip_path = download(f"{BASE_URL}/zip/{self.CC}.zip", os.path.join(self.work, "zip", f"{self.CC}.zip"))
		rows = read_zip_tsv(zip_path, f"{self.CC}.txt")
		pattern = re.compile(cfg["pattern"]) if cfg.get("pattern") else None
		attach_to = cfg.get("attach_to") or [lvl["source"] for lvl in reversed(self.config["levels"])]
		levels = self.config["levels"]
		source_to_level = {lvl["source"]: i for i, lvl in enumerate(levels)}

		# indexes: places by (parent code, normalized name); admin units by admin path
		place_index: dict[tuple, str] = {}
		if "P" in source_to_level:
			for code, u in self.level_units[source_to_level["P"]].items():
				place_index[(u["parent"], norm(u["name"]))] = code
				for alias in u["aliases"]:
					place_index.setdefault((u["parent"], norm(alias)), code)
		# admin units by full admin-code path, plus by their own (last) code when that is
		# unique nationwide: postal files sometimes use different upper-level codes
		admin_index: dict[str, dict[tuple, str]] = {}
		admin_last: dict[str, dict[str, str | None]] = {}
		for source, li in source_to_level.items():
			if source.startswith("ADM"):
				depth = self._depth(source)
				admin_index[source] = {u["path"][:depth]: code for code, u in self.level_units[li].items()}
				last: dict[str, str | None] = {}
				for code, u in self.level_units[li].items():
					own = u["path"][depth - 1]
					last[own] = None if own in last and last[own] != code else code
				admin_last[source] = last

		# admin units by (parent code, name) for postal files whose admin codes differ
		# from the gazetteer's (they often carry names in a different code scheme)
		admin_by_name: dict[str, dict[tuple, str | None]] = {}
		for source, li in source_to_level.items():
			if source.startswith("ADM"):
				index: dict[tuple, str | None] = {}
				for code, u in self.level_units[li].items():
					for label in [u["name"], *u["aliases"]]:
						key = (u["parent"], norm(label))
						index[key] = None if key in index and index[key] != code else code
				admin_by_name[source] = index

		def find_admin_by_names(source: str, names: tuple) -> str | None:
			"""Walk the configured admin levels top-down matching the row's admin names."""
			parent = None
			for lvl in levels:
				src = lvl["source"]
				if not src.startswith("ADM"):
					continue
				depth = self._depth(src)
				name = names[depth - 1] if depth <= len(names) else ""
				if not name:
					return None
				parent = admin_by_name.get(src, {}).get((parent, norm(name)))
				if parent is None:
					return None
				if src == source:
					return parent
			return None

		def find_admin(source: str, path: tuple, names: tuple = ()) -> str | None:
			depth = self._depth(source)
			code = admin_index.get(source, {}).get(tuple(path[:depth]))
			if code is None and depth <= len(path) and path[depth - 1]:
				code = admin_last.get(source, {}).get(path[depth - 1])
			# some postal files carry the GeoNames id itself as the admin code
			if (
				code is None
				and depth <= len(path)
				and path[depth - 1] in self.level_units[source_to_level[source]]
			):
				code = path[depth - 1]
			if code is None and names:
				code = find_admin_by_names(source, names)
			return code

		# last resort: a name that is unique nationwide at that level (names and aliases)
		name_index: dict[str, dict[str, set[str]]] = {}
		for source, li in source_to_level.items():
			index: dict[str, set[str]] = defaultdict(set)
			for code, u in self.level_units[li].items():
				index[norm(u["name"])].add(code)
				for alias in u["aliases"]:
					index[norm(alias)].add(code)
			name_index[source] = index

		def find_by_unique_name(source: str, name: str) -> str | None:
			codes = name_index.get(source, {}).get(norm(name)) or set()
			return next(iter(codes)) if len(codes) == 1 else None

		out: set[tuple[int, str, str]] = set()
		dropped = 0
		by_name = 0
		for r in rows:
			if len(r) < 9:
				continue
			postal = r[1].strip()
			if not postal or (pattern and not pattern.fullmatch(postal)):
				dropped += 1
				continue
			place_name, a1, a2, a3 = r[2], r[4], r[6], r[8]
			path = (a1, a2, a3)
			names = (r[3], r[5], r[7])
			target = None
			for source in attach_to:
				if source == "P" and "P" in source_to_level:
					parent_source = (
						levels[source_to_level["P"] - 1]["source"] if source_to_level["P"] > 0 else None
					)
					parent_code = None
					if parent_source:
						parent_code = find_admin(parent_source, path, names)
						if parent_code is None:
							continue
					code = place_index.get((parent_code, norm(place_name)))
					if code:
						target = (source_to_level["P"] + 1, code)
						break
				elif source in admin_index:
					code = find_admin(source, path, names)
					if code:
						target = (source_to_level[source] + 1, code)
						break
			if target is None:
				for source in attach_to:
					if source not in source_to_level:
						continue
					code = find_by_unique_name(source, place_name)
					if code:
						target = (source_to_level[source] + 1, code)
						by_name += 1
						break
			if target is None:
				dropped += 1
				continue
			out.add((target[0], target[1], postal))
		print(
			f"  postal codes: {len(out)} attached ({by_name} rows by unique name), {dropped} rows dropped (unmatched or invalid)"
		)
		return sorted(out)

	# -- output -------------------------------------------------------------

	def write(self, out_dir: str, postal: list[tuple[int, str, str]]) -> None:
		os.makedirs(out_dir, exist_ok=True)
		levels = self.config["levels"]
		counts = []
		for i in range(len(levels)):
			units = self.level_units[i]
			fname = f"level{i + 1}.csv"
			with open(os.path.join(out_dir, fname), "w", newline="", encoding="utf-8") as f:
				w = csv.writer(f, lineterminator="\n")
				headers = (["parent_code"] if i > 0 else []) + ["code", "name", "aliases"]
				w.writerow(headers)
				ordered = sorted(
					units.values(), key=lambda u: (u["parent"] or "", norm(u["name"]), u["code"])
				)
				for u in ordered:
					row = ([u["parent"]] if i > 0 else []) + [u["code"], u["name"], "|".join(u["aliases"])]
					w.writerow(row)
			counts.append(len(units))
		manifest = {
			"country_code": self.cc,
			"name": self.config["name"],
			"description": self.config.get("description", "")
			or f"{self.config['name']}: {' > '.join(l['label'] for l in levels)} from GeoNames ({', '.join(f'{c:,}' for c in counts)} records). Populated places with population >= {self.config.get('places', {}).get('min_population', 500)} plus administrative seats.",
			"version": self.config.get("version") or date.today().strftime("%Y.%m.%d"),
			"source": "https://www.geonames.org/ (GeoNames gazetteer and postal code dumps)",
			"source_url": f"{BASE_URL}/dump/{self.CC}.zip",
			"license": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) - data (c) GeoNames.org",
			"author": self.config.get(
				"author", "geo_extension maintainers (generated with tools/geonames/build_dataset.py)"
			),
			"updated": date.today().isoformat(),
			"levels": [
				{"file": f"level{i + 1}.csv", "label": l["label"], "target_field": l["target_field"]}
				for i, l in enumerate(levels)
			],
		}
		if postal:
			with open(os.path.join(out_dir, "postal_codes.csv"), "w", newline="", encoding="utf-8") as f:
				w = csv.writer(f, lineterminator="\n")
				w.writerow(["level", "code", "postal_code"])
				for level, code, pc in postal:
					w.writerow([level, code, pc])
			manifest["postal_codes"] = {"file": "postal_codes.csv"}
			if self.config.get("postal_codes", {}).get("pattern"):
				manifest["postal_codes"]["pattern"] = self.config["postal_codes"]["pattern"]
		with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
			json.dump(manifest, f, indent=2, ensure_ascii=False)
			f.write("\n")
		print(f"  wrote {out_dir} ({', '.join(str(c) for c in counts)} records)")


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument("countries", nargs="+", help="country codes present in countries.json")
	parser.add_argument("--config", default=os.path.join(HERE, "countries.json"))
	parser.add_argument("--work", default=os.path.join(HERE, ".work"), help="download cache directory")
	parser.add_argument("--out", required=True, help="parent directory for <cc>/ dataset directories")
	args = parser.parse_args(argv)

	with open(args.config, encoding="utf-8") as f:
		configs = json.load(f)
	for cc in args.countries:
		cc = cc.lower()
		if cc not in configs:
			print(f"{cc}: not in {args.config}", file=sys.stderr)
			return 1
		print(f"{cc}:")
		b = Builder(cc, configs[cc], args.work)
		b.load()
		b.build_levels()
		postal = b.build_postal()
		b.write(os.path.join(args.out, cc), postal)
	return 0


if __name__ == "__main__":
	sys.exit(main())
