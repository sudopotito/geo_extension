# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""Install/migrate/uninstall must leave Address untouched and clean up old versions."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

try:
	from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from geo_extension import install


class TestInstall(IntegrationTestCase):
	"""Note: recreating the legacy ``village`` Custom Field adds a column to tabAddress on the test site."""

	def setUp(self):
		super().setUp()
		# never leave customizations behind on the test site, whatever happens
		self.addCleanup(self._cleanup)

	def _cleanup(self):
		for name in frappe.get_all(
			"Property Setter",
			filters={
				"doc_type": "Address",
				"name": ("in", ("Address-fax-hidden", "Address-main-field_order")),
			},
			pluck="name",
		):
			frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
		for name in frappe.get_all(
			"Property Setter",
			filters={"doc_type": "Address", "property": "fieldtype", "value": "Autocomplete"},
			pluck="name",
		):
			frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=True)
		if frappe.db.exists("Custom Field", "Address-village"):
			frappe.delete_doc("Custom Field", "Address-village", ignore_permissions=True, force=True)
		for name in frappe.get_all("Address", filters={"address_title": "Legacy Test"}, pluck="name"):
			frappe.delete_doc("Address", name, ignore_permissions=True, force=True)
		frappe.clear_cache(doctype="Address")
		# creating a Custom Field runs DDL, which commits implicitly; commit the cleanup too
		frappe.db.commit()

	def _address_property_setters(self):
		return frappe.get_all(
			"Property Setter",
			filters={"doc_type": "Address", "property": ("in", ("fieldtype", "field_order"))},
			fields=["name", "field_name", "property", "value"],
		)

	def test_fresh_install_makes_no_changes(self):
		before = self._address_property_setters()
		custom_before = frappe.get_all("Custom Field", filters={"dt": "Address"}, pluck="name")
		install.after_install()
		install.after_migrate()
		self.assertEqual(self._address_property_setters(), before)
		self.assertEqual(
			frappe.get_all("Custom Field", filters={"dt": "Address"}, pluck="name"), custom_before
		)
		self.assertNotIn("village", [df.fieldname for df in frappe.get_meta("Address").fields])

	def test_legacy_customizations_are_removed(self):
		# recreate what geo_extension <= 1.4 used to install
		for fieldname in ("state", "city", "county"):
			make_property_setter("Address", fieldname, "fieldtype", "Autocomplete", "Data", for_doctype=False)
		make_property_setter("Address", None, "field_order", '["address_title"]', "Text", for_doctype=True)
		create_custom_fields(
			{
				"Address": [
					{
						"fieldname": "village",
						"label": "Village/Ward/Barangay",
						"fieldtype": "Autocomplete",
						"insert_after": "city",
					}
				]
			},
			ignore_validate=True,
		)
		self.assertTrue(frappe.db.exists("Custom Field", "Address-village"))
		self.assertEqual(len(self._address_property_setters()), 4)

		doc = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "Legacy Test",
				"address_type": "Billing",
				"address_line1": "1 Old Street",
				"city": "Cebu City",
				"country": "Philippines",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Address", doc.name, "village", "Lahug", update_modified=False)

		removed = install.remove_legacy_customizations()

		self.assertEqual(len(removed["property_setters"]), 4)
		self.assertEqual(removed["custom_fields"], ["Address-village"])
		self.assertEqual(self._address_property_setters(), [])
		self.assertFalse(frappe.db.exists("Custom Field", "Address-village"))
		self.assertEqual(frappe.get_meta("Address").get_field("state").fieldtype, "Data")
		# old barangay values are preserved in the native county field
		self.assertEqual(frappe.db.get_value("Address", doc.name, "county"), "Lahug")

		# running again is a no-op
		self.assertEqual(
			install.remove_legacy_customizations(), {"property_setters": [], "custom_fields": []}
		)

	def test_foreign_property_setters_are_kept(self):
		make_property_setter("Address", "fax", "hidden", "1", "Check", for_doctype=False)
		install.remove_legacy_customizations()
		self.assertTrue(
			frappe.db.exists(
				"Property Setter", {"doc_type": "Address", "field_name": "fax", "property": "hidden"}
			)
		)
