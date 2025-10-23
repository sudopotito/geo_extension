# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt


import json

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

ADDRESS = "Address"
AC_FIELDS = ["state", "county", "city", "barangay"]
SEGMENT_FIELDS = ["state", "county", "city", "barangay", "country"]


def before_install():
	pass


def after_install(force: bool = False):
	setup_custom_fields(force)
	setup_property_setters()
	frappe.db.commit()


def setup_custom_fields(force: bool = False):
	custom_fields = {
		ADDRESS: [
			{
				"fieldname": "barangay",
				"label": "Barangay",
				"fieldtype": "Autocomplete",
				"insert_after": "city",
			}
		]
	}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)


def setup_property_setters():
	"""
	1) Force fieldtypes → Autocomplete for select fields (when those fields exist).
	2) Reorder just the target slice to live between address_line2 and pincode.
	   Falls back to address_line1 if address_line2 isn't present.
	"""
	# 1) Fieldtypes → Autocomplete (only touch fields that exist)
	for fieldname in AC_FIELDS:
		_ensure_property_if_exists(ADDRESS, fieldname, "fieldtype", "Autocomplete", "Data")

	# 2) Re-order
	_ensure_field_order_slice(
		doctype=ADDRESS,
		segment_start="address_line2",
		segment_end="pincode",
		segment_start_fallback="address_line1",
		desired_between=SEGMENT_FIELDS,
	)


def _ensure_property_if_exists(doctype: str, fieldname: str, prop: str, value: str, property_type: str):
	"""
	Create/update a Property Setter for a specific field only if that field exists
	(either as a standard DocField or a Custom Field).
	"""
	if not _docfield_exists(doctype, fieldname):
		return

	ps = frappe.get_all(
		"Property Setter",
		filters={"doc_type": doctype, "field_name": fieldname, "property": prop},
		fields=["name", "value"],
		limit=1,
	)
	if ps:
		if ps[0].value != value:
			doc = frappe.get_doc("Property Setter", ps[0].name)
			doc.value = value
			doc.save(ignore_permissions=True)
		return

	make_property_setter(
		doctype=doctype,
		fieldname=fieldname,
		property=prop,
		value=value,
		property_type=property_type,
		for_doctype=False,
	)


def _docfield_exists(doctype: str, fieldname: str) -> bool:
	"""
	Return True if the field exists as a standard DocField or a Custom Field.
	"""
	return bool(
		frappe.get_all("DocField", filters={"parent": doctype, "fieldname": fieldname}, limit=1)
		or frappe.get_all("Custom Field", filters={"dt": doctype, "fieldname": fieldname}, limit=1)
	)


def _ensure_field_order_slice(
	doctype: str,
	segment_start: str,
	segment_end: str,
	desired_between: list[str],
	segment_start_fallback: str | None = None,
):
	"""
	Reorder only a subset of fields (desired_between) to live strictly between
	segment_start and segment_end. Preserve everything else exactly as-is.
	Only fields that actually exist on the DocType are considered.
	Writes a single doctype-level 'field_order' property when needed.
	"""
	meta = frappe.get_meta(doctype)
	current_order = [df.fieldname for df in meta.fields if df.fieldname]

	# Resolve start boundary with fallback
	start_boundary = (
		segment_start
		if segment_start in current_order
		else (segment_start_fallback if segment_start_fallback in current_order else None)
	)

	# Ensure boundaries exist
	if not start_boundary or segment_end not in current_order:
		return

	def _idx(name: str, order: list[str]) -> int:
		return order.index(name)

	# Only reorder fields that exist today
	existing_targets = [f for f in desired_between if f in current_order]
	if not existing_targets:
		return

	# Remove targets globally to avoid dupes
	order = [f for f in current_order if f not in existing_targets]

	# Compute boundaries after removals
	start_idx = _idx(start_boundary, order) + 1
	end_idx = _idx(segment_end, order)

	# Insert point must be before the end boundary
	insert_idx = min(max(start_idx, 0), end_idx)

	# Insert in the requested order
	for i, f in enumerate(existing_targets):
		order.insert(insert_idx + i, f)

	# Write doctype-level field_order only if changed
	if order != current_order:
		_set_doctype_field_order(doctype, order)


def _set_doctype_field_order(doctype: str, order: list[str]):
	"""
	Upsert a doctype-level field_order property setter with the given order.
	Detect DocType-level PS by field_name IS NULL or '' (no DB column 'for_doctype').
	"""
	value = json.dumps(order)

	# Look for an existing DocType-level property setter (field_name NULL or '')
	ps = frappe.db.sql(
		"""
        SELECT name, value
        FROM `tabProperty Setter`
        WHERE doc_type = %s
          AND property = 'field_order'
          AND (field_name IS NULL OR field_name = '')
        LIMIT 1
        """,
		(doctype,),
		as_dict=True,
	)

	if ps:
		if ps[0]["value"] != value:
			doc = frappe.get_doc("Property Setter", ps[0]["name"])
			doc.value = value
			doc.save(ignore_permissions=True)
	else:
		make_property_setter(
			doctype=doctype,
			fieldname=None,
			property="field_order",
			value=value,
			property_type="Text",
			for_doctype=True,
		)
