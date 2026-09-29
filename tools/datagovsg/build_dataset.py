#!/usr/bin/env python3
# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Generate the Singapore dataset from the URA Master Plan planning areas on data.gov.sg.

Source: Urban Redevelopment Authority, "Master Plan 2025 Planning Area Boundary (No Sea)",
https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view
License: Singapore Open Data Licence v1.0 (https://data.gov.sg/open-data-licence)

Usage::

    python tools/datagovsg/build_dataset.py --out geo_extension/setup/data/countries [--geojson file]

Produces a single level (Planning Area -> city) with the URA planning-area
code as the stable id. Singapore postal codes identify individual buildings,
so none are shipped.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import date

DATASET_ID = "d_2cc750190544007400b2cfd5d7f53209"
POLL_URL = f"https://api-open.data.gov.sg/v1/public/api/datasets/{DATASET_ID}/poll-download"


def fetch_geojson() -> dict:
	with urllib.request.urlopen(POLL_URL, timeout=60) as r:  # noqa: S310
		url = json.load(r)["data"]["url"]
	with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310
		return json.load(r)


def title(name: str) -> str:
	small = {"and", "of"}
	words = []
	for w in name.lower().split():
		words.append(w if w in small and words else "-".join(p.capitalize() for p in w.split("-")))
	return " ".join(words)


def main(argv=None) -> int:
	p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
	p.add_argument("--out", required=True)
	p.add_argument("--geojson", help="use an already downloaded GeoJSON file")
	args = p.parse_args(argv)
	data = json.load(open(args.geojson, encoding="utf-8")) if args.geojson else fetch_geojson()

	areas = {}
	for feature in data["features"]:
		props = feature["properties"]
		code, name, region = props.get("PLN_AREA_C"), props.get("PLN_AREA_N"), props.get("REGION_N")
		if code and name:
			areas[code] = (title(name), title(region or ""))
	out_dir = os.path.join(args.out, "sg")
	os.makedirs(out_dir, exist_ok=True)
	with open(os.path.join(out_dir, "level1.csv"), "w", newline="", encoding="utf-8") as f:
		w = csv.writer(f, lineterminator="\n")
		w.writerow(["code", "name", "aliases"])
		for code, (name, _region) in sorted(areas.items(), key=lambda kv: kv[1][0]):
			w.writerow([code, name, ""])
	manifest = {
		"country_code": "sg",
		"name": "Singapore",
		"description": f"Singapore: {len(areas)} URA Master Plan 2025 planning areas. Codes are URA planning-area codes.",
		"version": date.today().strftime("%Y.%m.%d"),
		"source": "Urban Redevelopment Authority via data.gov.sg - Master Plan 2025 Planning Area Boundary (No Sea)",
		"source_url": f"https://data.gov.sg/datasets/{DATASET_ID}/view",
		"license": "Singapore Open Data Licence v1.0 (https://data.gov.sg/open-data-licence)",
		"author": "geo_extension maintainers (generated with tools/datagovsg/build_dataset.py)",
		"updated": date.today().isoformat(),
		"levels": [{"file": "level1.csv", "label": "Planning Area", "target_field": "city"}],
	}
	with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
		json.dump(manifest, f, indent=2, ensure_ascii=False)
		f.write("\n")
	print(f"wrote {out_dir}: {len(areas)} planning areas")
	return 0


if __name__ == "__main__":
	sys.exit(main())
