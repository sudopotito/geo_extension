#!/usr/bin/env python3
# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Generate the Philippines dataset from the official PSGC publication.

Source: Philippine Statistics Authority, "PSGC Publication Datafile" (xlsx),
https://psa.gov.ph/classification/psgc (quarterly). Use constraint: acknowledge
the PSA as the source.

Usage::

    python tools/psgc/build_dataset.py PSGC-2Q-2026-Publication-Datafile.xlsx \\
        --out geo_extension/setup/data/countries [--postal-zip /path/to/geonames/PH.zip]

Levels produced (10-digit PSGC codes are the stable ids):

    1  Province            -> state    (provinces + "Metro Manila" for the NCR)
    2  City/Municipality   -> city
    3  Barangay            -> county

Rules:
- NCR cities/municipality (Pateros) hang under a synthetic "Metro Manila" unit
  whose code is the NCR region code (1300000000).
- Barangays of Manila's sub-municipalities are attached to the City of Manila.
- A city whose province prefix has no province row (City of Isabela, which PSA
  files under Region IX with a special province code) is attached to the
  province it lies in geographically (Basilan). Documented in the manifest.
- Aliases: PSA "Old names" and the "X City" / "City of X" variant.
- Postal codes (optional) come from the GeoNames postal-code dump (CC BY 4.0);
  a code is attached only when the GeoNames place name and province match a
  city/municipality exactly (after normalisation). Everything else is dropped.

Requires ``openpyxl``.
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
import zipfile
from collections import defaultdict
from datetime import date

NCR_CODE = "1300000000"
NCR_NAME = "Metro Manila"
NCR_ALIASES = ["National Capital Region", "NCR"]
MANILA_CODE = "1380600000"

#: Highly urbanised / independent component cities are coded by the PSA at
#: province level (no province row). For address entry they belong to the
#: province they lie in geographically. City name -> province name.
INDEPENDENT_CITIES = {
	"City of Baguio": "Benguet",
	"City of Angeles": "Pampanga",
	"City of Olongapo": "Zambales",
	"City of Lucena": "Quezon",
	"City of Puerto Princesa": "Palawan",
	"City of Iloilo": "Iloilo",
	"City of Bacolod": "Negros Occidental",
	"City of Cebu": "Cebu",
	"City of Lapu-Lapu": "Cebu",
	"City of Mandaue": "Cebu",
	"City of Tacloban": "Leyte",
	"City of Zamboanga": "Zamboanga del Sur",
	"City of Cagayan De Oro": "Misamis Oriental",
	"City of Iligan": "Lanao del Norte",
	"City of Davao": "Davao del Sur",
	"City of General Santos": "South Cotabato",
	"City of Butuan": "Agusan del Norte",
	"City of Isabela": "Basilan",
	"City of Cotabato": "Maguindanao del Norte",
	"City of Santiago": "Isabela",
	"City of Ormoc": "Leyte",
	"City of Naga": "Camarines Sur",
	"City of Dagupan": "Pangasinan",
}

#: Province-level areas that are not provinces but need a level-1 entry.
SYNTHETIC_PROVINCES = {
	"19999": ("1999900000", "Special Geographic Area", ["SGA", "Bangsamoro Special Geographic Area"]),
}

ABBREVIATIONS = {"sta.": "santa", "sto.": "santo", "gen.": "general", "sn.": "san", "mt.": "mount", "ft.": "fort"}


def norm(text: str) -> str:
	nfkd = unicodedata.normalize("NFKD", text or "")
	s = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
	return re.sub(r"\s+", " ", s).strip().casefold()


def name_variants(name: str) -> list[str]:
	"""Spelling variants used when matching external names (postal data) to PSGC names."""
	out = [name]
	base = re.sub(r"\s*\(.*?\)\s*", " ", name).strip()  # drop "(formerly X)"
	inner = re.findall(r"\((.*?)\)", name)
	for candidate in [base, *inner]:
		if candidate and candidate not in out:
			out.append(candidate)
	expanded = []
	for candidate in out:
		words = [ABBREVIATIONS.get(w.lower(), w) for w in candidate.split()]
		joined = " ".join(words)
		if joined not in out and joined not in expanded:
			expanded.append(joined)
	out.extend(expanded)
	for candidate in list(out):
		out.extend(v for v in city_aliases(candidate) if v not in out)
	return out


def city_aliases(name: str) -> list[str]:
	m = re.fullmatch(r"City of (.+)", name)
	if m:
		return [f"{m.group(1)} City"]
	m = re.fullmatch(r"(.+) City", name)
	if m:
		return [f"City of {m.group(1)}"]
	return []


def read_psgc(xlsx: str) -> list[dict]:
	import openpyxl

	wb = openpyxl.load_workbook(xlsx, read_only=True)
	ws = wb["PSGC"]
	rows = ws.iter_rows(values_only=True)
	header = [str(h or "").strip().split("\n")[0] for h in next(rows)]
	col = {h: i for i, h in enumerate(header)}
	code_i, name_i, level_i = col["10-digit PSGC"], col["Name"], col["Geographic Level"]
	old_i = col.get("Old names")
	out = []
	for r in rows:
		code = str(r[code_i] or "").strip()
		name = str(r[name_i] or "").strip()
		level = str(r[level_i] or "").strip()
		if not (re.fullmatch(r"\d{10}", code) and name and level):
			continue
		old = str(r[old_i] or "").strip() if old_i is not None else ""
		out.append({"code": code, "name": re.sub(r"\s+", " ", name), "level": level, "old": old})
	meta = {}
	for r in wb["Metadata"].iter_rows(values_only=True, max_row=10):
		if r and r[0] and r[1]:
			meta[str(r[0]).strip(": ")] = str(r[1]).strip()
	return out, meta


def build(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict], list[str]]:
	notes: list[str] = []
	provinces = {r["code"]: r for r in rows if r["level"] == "Prov"}
	cities = {r["code"]: r for r in rows if r["level"] in ("City", "Mun")}
	submun = {r["code"]: r for r in rows if r["level"] == "SubMun"}

	level1 = [{"code": NCR_CODE, "name": NCR_NAME, "aliases": list(NCR_ALIASES)}]
	for code, r in provinces.items():
		level1.append({"code": code, "name": r["name"], "aliases": [a for a in [r["old"]] if a]})
	for code, name, aliases in SYNTHETIC_PROVINCES.values():
		level1.append({"code": code, "name": name, "aliases": list(aliases)})
	level1_codes = {u["code"] for u in level1}
	province_by_name = {norm(u["name"]): u["code"] for u in level1}

	level2 = []
	city_parent: dict[str, str] = {}
	for code, r in cities.items():
		prov_code = code[:5] + "00000"
		if prov_code in provinces:
			parent = prov_code
		elif code.startswith("13"):
			parent = NCR_CODE
		elif code[:5] in SYNTHETIC_PROVINCES:
			parent = SYNTHETIC_PROVINCES[code[:5]][0]
		elif r["name"] in INDEPENDENT_CITIES:
			parent = province_by_name.get(norm(INDEPENDENT_CITIES[r["name"]]))
			if parent is None:
				notes.append(f"skipped {r['name']} ({code}): province '{INDEPENDENT_CITIES[r['name']]}' not found")
				continue
			notes.append(f"{r['name']} ({code}) listed under {INDEPENDENT_CITIES[r['name']]}")
		else:
			notes.append(f"skipped {r['name']} ({code}): no province (add it to INDEPENDENT_CITIES)")
			continue
		aliases = [a for a in [r["old"]] if a] + city_aliases(r["name"])
		level2.append({"code": code, "parent": parent, "name": r["name"], "aliases": aliases})
		city_parent[code] = parent
	level2_codes = {u["code"] for u in level2}

	level3 = []
	skipped_bgy = 0
	for r in rows:
		if r["level"] != "Bgy":
			continue
		code = r["code"]
		parent = code[:7] + "000"
		if parent in submun:
			parent = code[:5] + "00000"  # sub-municipality -> its city (Manila)
		if parent not in level2_codes:
			skipped_bgy += 1
			continue
		level3.append({"code": code, "parent": parent, "name": r["name"], "aliases": [a for a in [r["old"]] if a]})
	if skipped_bgy:
		notes.append(f"skipped {skipped_bgy} barangays without a city/municipality")
	assert all(u["parent"] in level1_codes for u in level2)
	for units in (level1, level2, level3):
		drop_ambiguous_aliases(units)
	return level1, level2, level3, notes


def drop_ambiguous_aliases(units: list[dict]) -> None:
	"""Remove aliases that equal a sibling's name or are claimed by several siblings."""
	names = defaultdict(set)
	alias_owner = defaultdict(set)
	for u in units:
		names[u.get("parent")].add(norm(u["name"]))
		for a in u["aliases"]:
			alias_owner[(u.get("parent"), norm(a))].add(u["code"])
	for u in units:
		u["aliases"] = [
			a
			for a in u["aliases"]
			if norm(a) not in names[u.get("parent")] and len(alias_owner[(u.get("parent"), norm(a))]) == 1
		]


def match_postal(zip_path: str, level1: list[dict], level2: list[dict]) -> tuple[list[tuple[int, str, str]], int]:
	with zipfile.ZipFile(zip_path) as z, z.open("PH.txt") as f:
		rows = list(csv.reader(io.TextIOWrapper(f, encoding="utf-8", newline=""), delimiter="\t", quoting=csv.QUOTE_NONE))
	prov_by_key: dict[str, str] = {}
	for u in level1:
		for key in [u["name"], *u["aliases"]]:
			prov_by_key[norm(key)] = u["code"]
	city_by_key: dict[tuple[str, str], str] = {}
	for u in level2:
		for key in [u["name"], *u["aliases"]]:
			city_by_key.setdefault((u["parent"], norm(key)), u["code"])
	# names that identify exactly one city nationwide (for rows without province info)
	unique_city: dict[str, str | None] = {}
	for (_, key), code in city_by_key.items():
		unique_city[key] = None if key in unique_city and unique_city[key] != code else code

	out: set[tuple[int, str, str]] = set()
	dropped = 0
	for r in rows:
		if len(r) < 9:
			continue
		postal, place, admin1, admin2 = r[1].strip(), r[2], r[3], r[5]
		if not re.fullmatch(r"\d{4}", postal):
			dropped += 1
			continue
		prov_name = re.sub(r"^Province of ", "", admin2 or "").strip()
		prov = prov_by_key.get(norm(prov_name)) if prov_name else None
		if prov is None and norm(admin1) in ("national capital region", "metro manila"):
			prov = NCR_CODE
		city = None
		variants = name_variants(place)
		if prov is not None:
			for variant in variants:
				city = city_by_key.get((prov, norm(variant)))
				if city:
					break
		elif not admin1 and not admin2:
			for variant in variants:
				city = unique_city.get(norm(variant))
				if city:
					break
		if city is None:
			dropped += 1
			continue
		out.add((2, city, postal))
	return sorted(out), dropped


def write(out_dir: str, level1, level2, level3, postal, meta, notes, source_file: str) -> None:
	os.makedirs(out_dir, exist_ok=True)

	def dump(fname, units, with_parent):
		with open(os.path.join(out_dir, fname), "w", newline="", encoding="utf-8") as f:
			w = csv.writer(f, lineterminator="\n")
			w.writerow((["parent_code"] if with_parent else []) + ["code", "name", "aliases"])
			for u in sorted(units, key=lambda u: (u.get("parent", ""), norm(u["name"]), u["code"])):
				w.writerow(([u["parent"]] if with_parent else []) + [u["code"], u["name"], "|".join(u["aliases"])])

	dump("level1.csv", level1, False)
	dump("level2.csv", level2, True)
	dump("level3.csv", level3, True)
	pub = meta.get("Publication date", "")
	manifest = {
		"country_code": "ph",
		"name": "Philippines",
		"description": (
			f"Philippines: {len(level1)} provinces (incl. Metro Manila), {len(level2):,} cities and municipalities "
			f"and {len(level3):,} barangays from the official PSGC publication ({pub}). Codes are 10-digit PSGC codes. "
			"City of Isabela is listed under Basilan; barangays of Manila's sub-municipalities are listed under the City of Manila."
		),
		"version": date.today().strftime("%Y.%m.%d"),
		"source": "Philippine Statistics Authority - Philippine Standard Geographic Code (PSGC), " + os.path.basename(source_file),
		"source_url": "https://psa.gov.ph/classification/psgc",
		"license": "Free to use with acknowledgement of the Philippine Statistics Authority (PSA) as the source (PSGC use constraints)",
		"author": "David Webb Espiritu <davidwebbespiritu@gmail.com> | https://www.linkedin.com/in/davidwebbespiritu",
		"updated": date.today().isoformat(),
		"levels": [
			{"file": "level1.csv", "label": "Province", "target_field": "state"},
			{"file": "level2.csv", "label": "City/Municipality", "target_field": "city"},
			{"file": "level3.csv", "label": "Barangay", "target_field": "county"},
		],
	}
	if postal:
		with open(os.path.join(out_dir, "postal_codes.csv"), "w", newline="", encoding="utf-8") as f:
			w = csv.writer(f, lineterminator="\n")
			w.writerow(["level", "code", "postal_code"])
			w.writerows(postal)
		manifest["postal_codes"] = {"file": "postal_codes.csv", "pattern": "^[0-9]{4}$"}
		manifest["description"] += (
			f" Postal codes ({len({p for _, _, p in postal}):,} for {len({c for _, c, _ in postal}):,} cities/municipalities) "
			"from the GeoNames postal-code dump (CC BY 4.0), matched by place and province name."
		)
	with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
		json.dump(manifest, f, indent=2, ensure_ascii=False)
		f.write("\n")
	for n in notes:
		print("  note:", n)
	print(f"  wrote {out_dir}: {len(level1)} / {len(level2)} / {len(level3)} records, {len(postal)} postal rows")


def main(argv=None) -> int:
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("xlsx", help="PSGC Publication Datafile (.xlsx)")
	p.add_argument("--out", required=True, help="parent directory for the ph/ dataset directory")
	p.add_argument("--postal-zip", help="GeoNames export/zip/PH.zip for postal codes (optional)")
	args = p.parse_args(argv)
	rows, meta = read_psgc(args.xlsx)
	level1, level2, level3, notes = build(rows)
	postal: list = []
	if args.postal_zip:
		postal, dropped = match_postal(args.postal_zip, level1, level2)
		print(f"  postal: {len(postal)} rows attached, {dropped} GeoNames rows dropped")
	write(os.path.join(args.out, "ph"), level1, level2, level3, postal, meta, notes, args.xlsx)
	return 0


if __name__ == "__main__":
	sys.exit(main())
