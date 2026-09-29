# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
One-time upgrade patch for sites that ran geo_extension <= 1.4.

Version 2.0 makes **no schema or layout changes** to Address: no Custom Fields,
no Property Setters. Earlier releases did (an Autocomplete fieldtype on
state/city/county, a DocType-level field order and, before 1.4, a ``village``
Custom Field). This patch removes those leftovers so upgraded sites end up
identical to fresh installs. Fresh installs never run it: Frappe marks an
app's patches as completed when the app is installed.
"""

import json

import frappe

ADDRESS = "Address"

#: Property Setters created by geo_extension <= 1.4 (field_name, property, value)
LEGACY_PROPERTY_SETTERS = [
	("state", "fieldtype", "Autocomplete"),
	("city", "fieldtype", "Autocomplete"),
	("county", "fieldtype", "Autocomplete"),
]

#: contiguous slice geo_extension <= 1.4 wrote into the Address field order
LEGACY_FIELD_ORDER = ["state", "city", "county", "country"]

#: Custom Field created by geo_extension < 1.4
LEGACY_CUSTOM_FIELD = "village"
LEGACY_CUSTOM_FIELD_LABELS = {"Village/Ward/Barangay", "Barangay"}


def execute():
	remove_legacy_customizations()


def remove_legacy_customizations() -> dict:
	"""Delete Address customizations made by earlier versions of this app. Idempotent."""
	removed = {"property_setters": [], "custom_fields": []}

	for field_name, prop, value in LEGACY_PROPERTY_SETTERS:
		for name in frappe.get_all(
			"Property Setter",
			filters={"doc_type": ADDRESS, "field_name": field_name, "property": prop, "value": value},
			pluck="name",
		):
			frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
			removed["property_setters"].append(name)

	# DocType-level field order written by geo_extension <= 1.4: it placed
	# state, city, county, country contiguously (LEGACY_FIELD_ORDER). An order that
	# does not carry that signature was set by the site and is left alone.
	for ps in frappe.get_all(
		"Property Setter",
		filters={"doc_type": ADDRESS, "property": "field_order", "field_name": ("is", "not set")},
		fields=["name", "value"],
	):
		if _is_legacy_field_order(ps.value):
			frappe.delete_doc("Property Setter", ps.name, ignore_permissions=True, force=True)
			removed["property_setters"].append(ps.name)

	custom_field = frappe.db.get_value(
		"Custom Field", {"dt": ADDRESS, "fieldname": LEGACY_CUSTOM_FIELD}, ["name", "label"], as_dict=True
	)
	if custom_field and custom_field.label in LEGACY_CUSTOM_FIELD_LABELS:
		_preserve_legacy_values()
		frappe.delete_doc("Custom Field", custom_field.name, ignore_permissions=True, force=True)
		removed["custom_fields"].append(custom_field.name)

	if removed["property_setters"] or removed["custom_fields"]:
		frappe.clear_cache(doctype=ADDRESS)
	return removed


def _is_legacy_field_order(value) -> bool:
	try:
		order = json.loads(value) if isinstance(value, str) else list(value or [])
	except ValueError:
		return False
	n = len(LEGACY_FIELD_ORDER)
	return any(order[i : i + n] == LEGACY_FIELD_ORDER for i in range(len(order) - n + 1))


def _preserve_legacy_values():
	"""Copy old ``village`` values into the native ``county`` field where it is empty.
	The database column itself is kept (Frappe never drops columns on its own)."""
	if not frappe.db.has_column(ADDRESS, LEGACY_CUSTOM_FIELD):
		return
	table = frappe.qb.DocType(ADDRESS)
	village = table[LEGACY_CUSTOM_FIELD]
	(
		frappe.qb.update(table)
		.set(table.county, village)
		.where((village.isnotnull()) & (village != "") & ((table.county.isnull()) | (table.county == "")))
	).run()
