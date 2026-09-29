# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
DEPRECATED compatibility shim for the pre-2.0 API.

Use ``geo_extension.api`` instead:

    geo_extension.geo_extension.locations.get_levels        -> geo_extension.api.get_hierarchy
    geo_extension.geo_extension.locations.get_level_options -> geo_extension.api.get_options

This module will be removed in a future release.
"""

import frappe

from geo_extension import api


@frappe.whitelist(allow_guest=True)
def get_levels(country: str):
	hierarchy = api.get_hierarchy(country)
	return [
		{
			"index": lvl["level"],
			"label": lvl["label"],
			"target_field": lvl["target_field"],
			"parent_level": lvl["level"] - 1 if lvl["level"] > 1 else None,
		}
		for lvl in hierarchy.get("levels", [])
	]


@frappe.whitelist(allow_guest=True)
def get_level_options(country: str, level_index: int, parent_code: str | None = None):
	return api.get_options(country, level_index, parent_code)
