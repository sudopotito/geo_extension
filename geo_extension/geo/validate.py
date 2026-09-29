# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Dataset validation.

Run before committing a dataset::

    bench geo-extension validate ph          # inside a bench
    python -m geo_extension.geo.validate ph  # anywhere (PYTHONPATH must include apps/geo_extension)

The checks are deliberately stricter than the runtime loader, which skips
unusable rows silently so that a small mistake never breaks address entry.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from geo_extension.geo import dataset as ds

ERROR = "error"
WARNING = "warning"

MANIFEST_REQUIRED = ("country_code", "levels")
MANIFEST_RECOMMENDED = ("name", "description", "version", "source", "license", "author")
MANIFEST_KNOWN = (
	set(MANIFEST_REQUIRED) | set(MANIFEST_RECOMMENDED) | {"source_url", "updated", "postal_codes"}
)
LEVEL_KNOWN = {"file", "label", "target_field"}
LEVEL_OBSOLETE = {"parent_level"}
POSTAL_KNOWN = {"file", "pattern"}


@dataclass
class Issue:
	severity: str
	message: str
	file: str | None = None
	line: int | None = None

	def __str__(self) -> str:
		where = ""
		if self.file:
			where = self.file
			if self.line:
				where += f":{self.line}"
			where += ": "
		return f"{self.severity.upper()}: {where}{self.message}"


@dataclass
class Report:
	code: str
	path: str
	issues: list[Issue] = field(default_factory=list)
	counts: list[int] = field(default_factory=list)
	postal_count: int = 0

	def add(self, severity: str, message: str, file: str | None = None, line: int | None = None) -> None:
		self.issues.append(Issue(severity, message, file, line))

	def error(self, message: str, file: str | None = None, line: int | None = None) -> None:
		self.add(ERROR, message, file, line)

	def warning(self, message: str, file: str | None = None, line: int | None = None) -> None:
		self.add(WARNING, message, file, line)

	@property
	def errors(self) -> list[Issue]:
		return [i for i in self.issues if i.severity == ERROR]

	@property
	def warnings(self) -> list[Issue]:
		return [i for i in self.issues if i.severity == WARNING]

	@property
	def ok(self) -> bool:
		return not self.errors

	def summary(self) -> str:
		counts = ", ".join(f"L{i + 1}={n}" for i, n in enumerate(self.counts)) or "no levels"
		postal = f", postal={self.postal_count}" if self.postal_count else ""
		status = "OK" if self.ok else "FAILED"
		return f"{self.code}: {status} ({counts}{postal}; {len(self.errors)} error(s), {len(self.warnings)} warning(s))"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _known_country_codes() -> set[str] | None:
	"""ISO alpha-2 codes known to Frappe; ``None`` when Frappe is unavailable."""
	try:
		import json

		import frappe

		path = frappe.get_app_path("frappe", "geo", "country_info.json")
		with open(path, encoding="utf-8") as f:
			data = json.load(f)
		return {v.get("code", "").lower() for v in data.values() if v.get("code")}
	except Exception:
		return None


def _check_manifest(
	report: Report, manifest: dict, require_known_country: bool = True
) -> tuple[list[ds.Level], str | None, re.Pattern | None]:
	mf = ds.MANIFEST_FILE

	for key in MANIFEST_REQUIRED:
		if key not in manifest:
			report.error(f"missing required property '{key}'", mf)
	for key in MANIFEST_RECOMMENDED:
		if not str(manifest.get(key) or "").strip():
			report.warning(f"missing recommended property '{key}'", mf)
	for key in manifest:
		if key not in MANIFEST_KNOWN:
			report.warning(f"unknown property '{key}' is ignored", mf)

	code = manifest.get("country_code")
	if code is not None:
		norm = ds.normalize_country_code(str(code))
		if not norm:
			report.error(f"country_code '{code}' is not a two-letter ISO 3166-1 alpha-2 code", mf)
		elif norm != report.code:
			report.error(f"country_code '{code}' does not match directory name '{report.code}'", mf)
		else:
			known = _known_country_codes()
			if known is not None and norm not in known:
				message = f"country_code '{norm}' is not a country code known to Frappe"
				if require_known_country:
					report.error(message, mf)
				else:
					report.warning(message + " (fine for a work-in-progress or test dataset)", mf)

	# levels
	raw_levels = manifest.get("levels")
	levels: list[ds.Level] = []
	if not isinstance(raw_levels, list) or not raw_levels:
		report.error("'levels' must be a non-empty list", mf)
		return levels, None, None
	if len(raw_levels) > ds.MAX_LEVELS:
		report.error(f"at most {ds.MAX_LEVELS} levels are supported (found {len(raw_levels)})", mf)

	seen_fields: dict[str, int] = {}
	seen_files: dict[str, int] = {}
	for i, entry in enumerate(raw_levels[: ds.MAX_LEVELS], start=1):
		if not isinstance(entry, dict):
			report.error(f"level {i} must be an object", mf)
			continue
		for key in entry:
			if key in LEVEL_OBSOLETE:
				report.warning(
					f"level {i}: '{key}' is obsolete (levels always nest in order) and is ignored", mf
				)
			elif key not in LEVEL_KNOWN:
				report.warning(f"level {i}: unknown property '{key}' is ignored", mf)

		label = ds.clean_text(entry.get("label"), 140)
		target = ds.clean_text(entry.get("target_field"), 64)
		file_name = ds.clean_text(entry.get("file"), 128)
		valid = True
		if not label:
			report.error(f"level {i}: 'label' is required", mf)
			valid = False
		if not target:
			report.error(f"level {i}: 'target_field' is required", mf)
			valid = False
		elif target not in ds.ALLOWED_TARGET_FIELDS:
			report.error(
				f"level {i}: target_field '{target}' is not one of {', '.join(ds.ALLOWED_TARGET_FIELDS)}", mf
			)
			valid = False
		elif target in seen_fields:
			report.error(
				f"level {i}: target_field '{target}' already used by level {seen_fields[target]}", mf
			)
			valid = False
		else:
			seen_fields[target] = i
		if not file_name:
			report.error(f"level {i}: 'file' is required", mf)
			valid = False
		else:
			path = ds.safe_join(report.path, file_name)
			if path is None:
				report.error(
					f"level {i}: file '{file_name}' must be a relative path inside the dataset directory", mf
				)
				valid = False
			elif not os.path.isfile(path):
				report.error(f"level {i}: file '{file_name}' does not exist", mf)
				valid = False
			elif file_name in seen_files:
				report.error(
					f"level {i}: file '{file_name}' already used by level {seen_files[file_name]}", mf
				)
				valid = False
			else:
				seen_files[file_name] = i
		if valid:
			levels.append(ds.Level(index=len(levels) + 1, label=label, target_field=target, file=file_name))

	if len(levels) != len(raw_levels[: ds.MAX_LEVELS]):
		# numbering would shift at runtime; make that explicit
		report.error("one or more levels are invalid; fix them before validating the CSV files", mf)
		levels = []

	# postal codes
	postal_file: str | None = None
	pattern: re.Pattern | None = None
	cfg = manifest.get(ds.POSTAL_KEY)
	if cfg is not None:
		if not isinstance(cfg, dict):
			report.error("'postal_codes' must be an object", mf)
		else:
			for key in cfg:
				if key not in POSTAL_KNOWN:
					report.warning(f"postal_codes: unknown property '{key}' is ignored", mf)
			postal_file = ds.clean_text(cfg.get("file"), 128) or None
			if not postal_file:
				report.error("postal_codes: 'file' is required", mf)
			else:
				path = ds.safe_join(report.path, postal_file)
				if path is None:
					report.error(
						f"postal_codes: file '{postal_file}' must be a relative path inside the dataset", mf
					)
					postal_file = None
				elif not os.path.isfile(path):
					report.error(f"postal_codes: file '{postal_file}' does not exist", mf)
					postal_file = None
			raw_pattern = cfg.get("pattern")
			if raw_pattern is not None:
				if not isinstance(raw_pattern, str) or not raw_pattern.strip():
					report.error("postal_codes: 'pattern' must be a non-empty regular expression string", mf)
				else:
					try:
						pattern = re.compile(raw_pattern)
					except re.error as e:
						report.error(f"postal_codes: invalid pattern: {e}", mf)

	return levels, postal_file, pattern


def _check_levels(report: Report, levels: list[ds.Level]) -> list[dict[str, str]]:
	"""Validate every level CSV. Returns per-level ``code -> parent_code`` maps."""
	code_maps: list[dict[str, str]] = []
	for level in levels:
		idx = level.index - 1
		path = ds.safe_join(report.path, level.file)
		fname = level.file
		codes: dict[str, str] = {}
		code_maps.append(codes)
		try:
			headers, rows = ds.read_csv_rows(path)
		except ds.DatasetError as e:
			report.error(str(e), fname)
			continue

		required = ds.LEVEL1_HEADERS if idx == 0 else ds.LEVELN_HEADERS
		missing = [h for h in required if h not in headers]
		if missing:
			report.error(
				f"missing required column(s): {', '.join(missing)} (found: {', '.join(headers) or 'none'})",
				fname,
			)
			continue
		extra = [h for h in headers if h and h not in required and h != ds.ALIASES_COLUMN]
		if extra:
			report.warning(f"extra column(s) ignored: {', '.join(extra)}", fname)
		if not rows:
			report.error("file has no data rows", fname)
			continue

		parents = code_maps[idx - 1] if idx > 0 else None
		name_keys: Counter = Counter()
		alias_keys: dict[tuple[str, str], list[str]] = defaultdict(list)
		orphans = 0
		for n, row in enumerate(rows, start=2):  # line 1 is the header
			raw_code = row.get("code", "")
			raw_name = row.get("name", "")
			code = ds.clean_code(raw_code)
			name = ds.clean_text(raw_name)
			if not raw_code:
				report.error("missing code", fname, n)
				continue
			if not code:
				report.error(f"invalid code '{raw_code}' (allowed: letters, digits, '.', '_', '-')", fname, n)
				continue
			if not name:
				report.error(f"missing name for code '{code}'", fname, n)
				continue
			if name != raw_name:
				report.warning(
					f"name '{raw_name}' contains unusual characters and will be shown as '{name}'", fname, n
				)
			parent = ""
			if idx > 0:
				raw_parent = row.get("parent_code", "")
				parent = ds.clean_code(raw_parent)
				if not raw_parent:
					report.error(f"missing parent_code for '{name}'", fname, n)
					continue
				if not parent:
					report.error(f"invalid parent_code '{raw_parent}'", fname, n)
					continue
				if parent == code:
					report.error(f"'{code}' references itself as parent", fname, n)
					continue
				if parent not in parents:
					orphans += 1
					if orphans <= 10:
						report.error(f"parent_code '{parent}' not found in {levels[idx - 1].file}", fname, n)
					continue
			if code in codes:
				report.error(f"duplicate code '{code}'", fname, n)
				continue
			for upper_idx, upper in enumerate(code_maps[:idx]):
				if code in upper:
					report.warning(
						f"code '{code}' is also used in {levels[upper_idx].file}; codes should be unique across levels",
						fname,
						n,
					)
					break
			codes[code] = parent
			name_keys[(parent, ds.normalize_name(name))] += 1
			raw_aliases = row.get(ds.ALIASES_COLUMN, "")
			if raw_aliases:
				aliases = ds.parse_aliases(raw_aliases)
				if not aliases:
					report.warning(f"aliases for '{name}' are empty after cleaning", fname, n)
				for alias in aliases:
					if ds.normalize_name(alias) == ds.normalize_name(name):
						report.warning(f"alias '{alias}' is the same as the name", fname, n)
					else:
						alias_keys[(parent, ds.normalize_name(alias))].append(name)

		if orphans > 10:
			report.error(f"... {orphans - 10} more row(s) with unknown parent_code", fname)
		for (parent, key), count in name_keys.items():
			if count > 1:
				scope = f" under parent '{parent}'" if parent else ""
				report.warning(f"name '{key}' appears {count} times{scope}", fname)
		for (parent, key), owners in alias_keys.items():
			scope = f" under parent '{parent}'" if parent else ""
			if (parent, key) in name_keys:
				report.warning(
					f"alias '{key}' of '{owners[0]}' is also the name of another unit{scope}", fname
				)
			elif len(owners) > 1:
				report.warning(
					f"alias '{key}' is used by {len(owners)} units{scope}: {', '.join(owners[:3])}", fname
				)

		if idx > 0 and parents:
			used = {p for p in codes.values()}
			childless = [p for p in parents if p not in used]
			if childless:
				report.warning(
					f"{len(childless)} of {len(parents)} unit(s) in {levels[idx - 1].file} have no children "
					f"(partial coverage), e.g. {', '.join(childless[:5])}",
					fname,
				)
	report.counts = [len(m) for m in code_maps]
	return code_maps


def _check_postal(
	report: Report,
	levels: list[ds.Level],
	code_maps: list[dict[str, str]],
	postal_file: str | None,
	pattern: re.Pattern | None,
) -> None:
	if not postal_file:
		return
	path = ds.safe_join(report.path, postal_file)
	try:
		headers, rows = ds.read_csv_rows(path)
	except ds.DatasetError as e:
		report.error(str(e), postal_file)
		return
	missing = [h for h in ds.POSTAL_HEADERS if h not in headers]
	if missing:
		report.error(f"missing required column(s): {', '.join(missing)}", postal_file)
		return
	if not rows:
		report.warning("postal code file has no data rows", postal_file)
		return

	seen: set[tuple[int, str, str]] = set()
	count = 0
	for n, row in enumerate(rows, start=2):
		raw_level = row.get("level", "")
		try:
			level = int(raw_level)
		except ValueError:
			report.error(f"invalid level '{raw_level}'", postal_file, n)
			continue
		if not (1 <= level <= len(levels)):
			report.error(f"level {level} does not exist (dataset has {len(levels)} level(s))", postal_file, n)
			continue
		raw_code = row.get("code", "")
		code = ds.clean_code(raw_code)
		if not code:
			report.error(f"invalid code '{raw_code}'", postal_file, n)
			continue
		if code not in code_maps[level - 1]:
			report.error(f"code '{code}' not found in {levels[level - 1].file}", postal_file, n)
			continue
		raw_postal = row.get("postal_code", "")
		postal = ds.clean_text(raw_postal, ds.MAX_POSTAL_LEN)
		if not postal:
			report.error("missing postal_code", postal_file, n)
			continue
		if pattern and not pattern.fullmatch(postal):
			report.error(f"postal code '{postal}' does not match pattern '{pattern.pattern}'", postal_file, n)
			continue
		key = (level, code, postal)
		if key in seen:
			report.warning(f"duplicate row for level {level} code '{code}' postal '{postal}'", postal_file, n)
			continue
		seen.add(key)
		count += 1
	report.postal_count = count


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------


def validate_path(path: str, code: str | None = None, require_known_country: bool = False) -> Report:
	"""
	Validate the dataset directory at ``path``.
	``require_known_country`` turns an unknown ISO code into an error (used for shipped datasets).
	"""
	path = os.path.abspath(path)
	code = ds.normalize_country_code(code or os.path.basename(path)) or os.path.basename(path)
	report = Report(code=code, path=path)

	if not os.path.isdir(path):
		report.error(f"directory does not exist: {path}")
		return report
	if not ds.normalize_country_code(os.path.basename(path)):
		report.error(f"directory name '{os.path.basename(path)}' must be a two-letter lowercase country code")

	try:
		manifest = ds.read_manifest(path)
	except ds.DatasetError as e:
		report.error(str(e), ds.MANIFEST_FILE)
		return report

	levels, postal_file, pattern = _check_manifest(report, manifest, require_known_country)
	if not levels:
		return report
	code_maps = _check_levels(report, levels)
	_check_postal(report, levels, code_maps, postal_file, pattern)
	return report


def validate_country(code: str, extra_roots: list[str] | None = None) -> Report:
	"""Validate a shipped (or extra-root) dataset by country code."""
	norm = ds.normalize_country_code(code)
	path = ds.find_country_path(norm, extra_roots) if norm else None
	if not path:
		report = Report(code=norm or code, path="")
		report.error(f"no dataset found for country code '{code}'")
		return report
	return validate_path(path, norm, require_known_country=True)


def validate_all(extra_roots: list[str] | None = None) -> list[Report]:
	return [validate_country(code, extra_roots) for code in ds.list_country_codes(extra_roots)]


def format_report(report: Report, verbose: bool = True) -> str:
	lines = [report.summary()]
	if verbose:
		lines.extend(f"  {issue}" for issue in report.issues)
	return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Validate geo_extension country datasets.")
	parser.add_argument("countries", nargs="*", help="country codes (default: all shipped datasets)")
	parser.add_argument("--path", help="validate an arbitrary dataset directory instead")
	parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
	parser.add_argument("--quiet", action="store_true", help="only print summaries")
	args = parser.parse_args(argv)

	if args.path:
		reports = [validate_path(args.path)]
	elif args.countries:
		reports = [validate_country(c) for c in args.countries]
	else:
		reports = validate_all()

	failed = False
	for report in reports:
		print(format_report(report, verbose=not args.quiet))
		if not report.ok or (args.strict and report.warnings):
			failed = True
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
