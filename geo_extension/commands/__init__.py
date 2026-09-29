# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Bench commands::

    bench geo-extension validate            # every shipped dataset
    bench geo-extension validate ph in      # specific countries
    bench geo-extension validate --path ./my/xx --strict
    bench geo-extension list
"""

import click

from geo_extension.geo import dataset as ds
from geo_extension.geo.validate import format_report, validate_all, validate_country, validate_path


@click.group("geo-extension")
def geo_extension():
	"""Geo Extension dataset tools."""


@geo_extension.command("validate")
@click.argument("countries", nargs=-1)
@click.option("--path", "path", default=None, help="Validate an arbitrary dataset directory.")
@click.option("--strict", is_flag=True, help="Treat warnings as failures.")
@click.option("--quiet", is_flag=True, help="Only print one summary line per dataset.")
def validate(countries, path, strict, quiet):
	"""Validate country datasets (manifest, hierarchy, postal codes)."""
	if path:
		reports = [validate_path(path)]
	elif countries:
		reports = [validate_country(c) for c in countries]
	else:
		reports = validate_all()

	failed = False
	for report in reports:
		click.echo(format_report(report, verbose=not quiet))
		if not report.ok or (strict and report.warnings):
			failed = True
	if failed:
		raise click.exceptions.Exit(1)


@geo_extension.command("list")
def list_datasets():
	"""List shipped datasets with their hierarchy and record counts."""
	for code in ds.list_country_codes():
		try:
			dataset = ds.get_dataset(code)
		except ds.DatasetError as e:
			click.echo(f"{code}: UNUSABLE ({e})")
			continue
		levels = " > ".join(f"{lvl.label} [{lvl.target_field}]" for lvl in dataset.levels)
		counts = "/".join(str(n) for n in dataset.counts())
		postal = f", {sum(len(v) for v in dataset.postal.values())} postal codes" if dataset.postal else ""
		click.echo(f"{code}: {levels} ({counts} records{postal})")


commands = [geo_extension]
