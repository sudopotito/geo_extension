# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""Integration tests for the whitelisted API and the Address DocType behaviour."""

import os

import frappe

try:
	from frappe.tests import IntegrationTestCase
except ImportError:  # Frappe v15
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase

from geo_extension import api
from geo_extension.geo import dataset as ds

TEST_ROOT = os.path.join(os.path.dirname(__file__), "data", "countries")


class GeoTestCase(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.flags.geo_extension_dataset_roots = [TEST_ROOT]
		ds.clear_cache()

	@classmethod
	def tearDownClass(cls):
		frappe.flags.geo_extension_dataset_roots = None
		ds.clear_cache()
		super().tearDownClass()


class TestAPI(GeoTestCase):
	def test_country_lookup_by_name_and_code(self):
		self.assertEqual(api.get_country_code("Philippines"), "ph")
		self.assertEqual(api.get_country_code("PH"), "ph")
		self.assertIsNone(api.get_country_code("Atlantis"))
		self.assertIsNone(api.get_country_code(""))
		self.assertIsNone(api.get_country_code(None))

	def test_hierarchy_for_supported_country(self):
		h = api.get_hierarchy("Philippines")
		self.assertTrue(h["supported"])
		self.assertEqual(h["country_code"], "ph")
		self.assertEqual([lvl["target_field"] for lvl in h["levels"]], ["state", "city", "county"])
		self.assertEqual(h["postal_codes"]["target_field"], "pincode")

	def test_hierarchy_for_unsupported_country(self):
		for country in ("Antarctica", "Atlantis", "", None):
			h = api.get_hierarchy(country)
			self.assertFalse(h["supported"])
			self.assertEqual(h["levels"], [])

	def test_broken_datasets_are_treated_as_unsupported(self):
		self.assertFalse(api.get_hierarchy("xb")["supported"])  # malformed JSON
		self.assertFalse(api.get_hierarchy("xc")["supported"])  # no usable level
		self.assertEqual(api.get_options("xb", 1), [])
		self.assertEqual(api.get_postal_codes("xb", 1, "A"), {"codes": [], "level": None})

	def test_options_are_scoped_to_parent(self):
		roots = api.get_options("xa", 1)
		self.assertEqual([r["label"] for r in roots], ["Empty Region", "Ñorth Region", "South Region"])
		self.assertEqual([r["value"] for r in api.get_options("xa", 2, "R1")], ["C1", "C2", "C4"])
		self.assertEqual([r["value"] for r in api.get_options("xa", "2", "R2")], ["C3"])
		self.assertEqual(api.get_options("xa", 2), [])  # no parent -> nothing, never the whole level
		self.assertEqual(api.get_options("xa", 2, "../R1"), [])
		self.assertEqual(api.get_options("xa", 9, "R1"), [])
		self.assertEqual(api.get_options("xa", 0), [])

	def test_options_txt_and_limit(self):
		self.assertEqual([r["label"] for r in api.get_options("xa", 2, "R1", txt="GAMMA")], ["Gamma City"])
		self.assertEqual(len(api.get_options("xa", 2, "R1", limit=1)), 1)
		self.assertEqual(len(api.get_options("xa", 2, "R1", limit="-5")), 1)

	def test_large_dataset_never_sends_whole_level(self):
		self.assertEqual(api.get_options("ph", 3), [])
		cebu = next(r for r in api.get_options("ph", 1) if r["label"] == "Cebu")
		cebu_city = next(r for r in api.get_options("ph", 2, cebu["value"]) if r["label"] == "City of Cebu")
		barangays = api.get_options("ph", 3, cebu_city["value"])
		self.assertTrue(0 < len(barangays) < 200)

	def test_resolve(self):
		chain = api.resolve("xa", '["south region", "Alpha City", "Nope"]')
		self.assertEqual(
			chain,
			[
				{"level": 1, "value": "R2", "label": "South Region"},
				{"level": 2, "value": "C3", "label": "Alpha City"},
			],
		)
		self.assertEqual(api.resolve("xa", ["Nowhere"]), [])
		self.assertEqual(api.resolve("xa", "not json"), [])
		self.assertEqual(api.resolve("xa", {"1": "Ñorth Region", "2": "Beta City"})[-1]["value"], "C2")
		self.assertEqual(api.resolve("Atlantis", ["x"]), [])

	def test_search(self):
		hits = api.search("xa", "alp")
		self.assertEqual([h["value"] for h in hits], ["C1", "C3"])
		self.assertEqual(
			hits[0]["path"],
			[
				{"level": 1, "value": "R1", "label": "Ñorth Region"},
				{"level": 2, "value": "C1", "label": "Alpha City", "aliases": ["Alfa", "Alpha"]},
			],
		)
		self.assertEqual([h["value"] for h in api.search("xa", "alfa")], ["C1"])
		self.assertEqual(api.search("xa", "a"), [])  # at least two characters
		self.assertEqual(api.search("xa", "east", level=3)[0]["value"], "D1")
		self.assertEqual(len(api.search("xa", "a", limit=1)), 0)
		self.assertEqual(len(api.search("xa", "re", limit=1)), 1)
		self.assertEqual(api.search("Atlantis", "alp"), [])
		self.assertEqual(api.search("xb", "alp"), [])
		self.assertIn(api.search, frappe.guest_methods)

	def test_options_carry_aliases(self):
		alpha = next(o for o in api.get_options("xa", 2, "R1") if o["value"] == "C1")
		self.assertEqual(alpha["aliases"], ["Alfa", "Alpha"])
		self.assertEqual(api.resolve("xa", ["north region", "ALFA"])[-1]["value"], "C1")

	def test_postal_codes(self):
		self.assertEqual(api.get_postal_codes("xa", 2, "C1"), {"codes": ["1000"], "level": 2})
		self.assertEqual(api.get_postal_codes("xa", 3, "D1"), {"codes": ["1000"], "level": 2})
		self.assertEqual(api.get_postal_codes("xa", 2, "C2"), {"codes": ["2000", "2001"], "level": 2})
		self.assertEqual(api.get_postal_codes("xa", 2, "C3"), {"codes": [], "level": None})
		self.assertEqual(api.get_postal_codes("xa", 2, ""), {"codes": [], "level": None})
		self.assertEqual(api.get_postal_codes("xa", 2, "C1; drop"), {"codes": [], "level": None})

	def test_endpoints_are_guest_accessible_and_read_only(self):
		for fn in (api.get_hierarchy, api.get_options, api.resolve, api.get_postal_codes, api.search):
			self.assertIn(fn, frappe.whitelisted, fn.__name__)
			self.assertIn(fn, frappe.guest_methods, fn.__name__)
		self.assertIn(api.get_supported_countries, frappe.whitelisted)
		self.assertNotIn(api.get_supported_countries, frappe.guest_methods)

	def test_guest_can_call_over_http(self):
		frappe.set_user("Guest")
		try:
			self.assertTrue(api.get_hierarchy("Philippines")["supported"])
			self.assertTrue(api.get_options("ph", 1))
		finally:
			frappe.set_user("Administrator")

	def test_supported_countries_listing(self):
		codes = [c["country_code"] for c in api.get_supported_countries()]
		self.assertIn("ph", codes)
		self.assertIn("xa", codes)
		self.assertNotIn("xb", codes)


class TestAddressStaysNative(GeoTestCase):
	"""The app must never make Address stricter than native Frappe."""

	def _make(self, **values):
		self.addCleanup(self._cleanup)
		doc = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": values.pop("address_title", "Geo Test"),
				"address_type": "Billing",
				"address_line1": "1 Test Street",
				"city": "Somewhere",
				"country": "Philippines",
				**values,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def _cleanup(self):
		for name in frappe.get_all("Address", filters={"address_title": "Geo Test"}, pluck="name"):
			frappe.delete_doc("Address", name, ignore_permissions=True, force=True)
		# reviewed: Custom Field DDL commits implicitly, so the cleanup must commit too
		frappe.db.commit()  # nosemgrep

	def test_native_fields_are_untouched(self):
		meta = frappe.get_meta("Address")
		for fieldname in ("state", "city", "county", "address_line2", "pincode"):
			self.assertEqual(meta.get_field(fieldname).fieldtype, "Data", fieldname)
		self.assertFalse(
			frappe.get_all(
				"Custom Field",
				filters={
					"dt": "Address",
					"fieldname": (
						"in",
						("village", "barangay", "province", "municipality", "region", "district"),
					),
				},
			)
		)
		self.assertFalse(
			frappe.get_all(
				"Property Setter",
				filters={"doc_type": "Address", "property": ("in", ("fieldtype", "field_order"))},
			)
		)

	def test_manual_values_not_in_dataset_are_accepted(self):
		doc = self._make(
			state="Made Up Province", city="Made Up City", county="Made Up Barangay", pincode="ABC-123"
		)
		self.assertEqual(doc.state, "Made Up Province")
		self.assertEqual(doc.county, "Made Up Barangay")

	def test_dataset_values_are_stored_as_plain_names(self):
		doc = self._make(state="Cebu", city="City of Cebu", county="Lahug")
		self.assertEqual(frappe.db.get_value("Address", doc.name, "city"), "City of Cebu")

	def test_unsupported_country_works_normally(self):
		doc = self._make(country="Antarctica", state="Ross Dependency", city="McMurdo")
		self.assertEqual(doc.country, "Antarctica")
