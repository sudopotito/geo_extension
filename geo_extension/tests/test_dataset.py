# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""Unit tests for the dataset engine. No site required."""

import os
import shutil
import tempfile
import unittest

from geo_extension.geo import dataset as ds

TEST_ROOT = os.path.join(os.path.dirname(__file__), "data", "countries")


class TestDatasetLoading(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		ds.clear_cache()
		cls.xa = ds.get_dataset("xa", [TEST_ROOT])

	def test_shipped_root_is_searched_last(self):
		roots = ds.dataset_roots([TEST_ROOT])
		self.assertEqual(roots[-1], ds.BUILTIN_ROOT)
		self.assertEqual(roots[0], TEST_ROOT)

	def test_missing_dataset_returns_none(self):
		self.assertIsNone(ds.get_dataset("zz", [TEST_ROOT]))
		self.assertIsNone(ds.get_dataset("", [TEST_ROOT]))
		self.assertIsNone(ds.get_dataset("not-a-code", [TEST_ROOT]))

	def test_country_code_is_case_insensitive(self):
		self.assertIs(ds.get_dataset("XA", [TEST_ROOT]), ds.get_dataset("xa", [TEST_ROOT]))

	def test_malformed_manifest_raises(self):
		with self.assertRaises(ds.DatasetError):
			ds.get_dataset("xb", [TEST_ROOT])

	def test_manifest_without_usable_levels_raises(self):
		with self.assertRaises(ds.DatasetError):
			ds.get_dataset("xc", [TEST_ROOT])

	def test_levels_and_mapping(self):
		self.assertEqual(self.xa.depth, 3)
		self.assertEqual([lvl.target_field for lvl in self.xa.levels], ["state", "city", "county"])
		self.assertEqual([lvl.label for lvl in self.xa.levels], ["Region", "City", "District"])
		self.assertEqual(self.xa.get_level(2).as_dict(), {"level": 2, "label": "City", "target_field": "city"})
		self.assertIsNone(self.xa.get_level(4))

	def test_roots_are_sorted_accent_insensitively(self):
		names = [u.name for u in self.xa.options(1)]
		self.assertEqual(names, ["Empty Region", "Ñorth Region", "South Region"])

	def test_children_are_filtered_by_parent(self):
		self.assertEqual([u.code for u in self.xa.options(2, "R1")], ["C1", "C2", "C4"])
		self.assertEqual([u.code for u in self.xa.options(2, "R2")], ["C3"])
		self.assertEqual(self.xa.options(2, "R3"), [])
		self.assertEqual(self.xa.options(2, None), [])  # lower levels always need a parent
		self.assertEqual(self.xa.options(3, "C1"), [self.xa.get_unit(3, "D1"), self.xa.get_unit(3, "D2")])

	def test_txt_filter_and_limit(self):
		self.assertEqual([u.name for u in self.xa.options(2, "R1", txt="beta")], ["Beta City"])
		self.assertEqual(len(self.xa.options(2, "R1", limit=2)), 2)

	def test_find_by_name_is_scoped_to_parent(self):
		# "Alpha City" exists under two regions; the parent decides which one is meant
		self.assertEqual(self.xa.find_by_name(2, "alpha city", "R1").code, "C1")
		self.assertEqual(self.xa.find_by_name(2, "ALPHA CITY", "R2").code, "C3")
		self.assertIsNone(self.xa.find_by_name(2, "Alpha City", "R3"))
		self.assertEqual(self.xa.find_by_name(1, "north region").code, "R1")

	def test_resolve_stops_at_first_mismatch(self):
		chain = self.xa.resolve(["South Region", "Alpha City", "Nowhere"])
		self.assertEqual([u.code for u in chain], ["R2", "C3"])
		self.assertEqual(self.xa.resolve(["Unknown", "Alpha City"]), [])
		self.assertEqual(self.xa.resolve([]), [])
		self.assertEqual([u.code for u in self.xa.resolve(["Ñorth Region", "beta city", "centre"])], ["R1", "C2", "D3"])

	def test_ancestors(self):
		unit = self.xa.get_unit(3, "D3")
		self.assertEqual([u.code for u in self.xa.ancestors(unit)], ["D3", "C2", "R1"])

	def test_postal_codes_walk_up_to_ancestors(self):
		self.assertEqual(self.xa.postal_codes_for(2, "C1"), (["1000"], 2))
		self.assertEqual(self.xa.postal_codes_for(3, "D1"), (["1000"], 2))  # district inherits from city
		self.assertEqual(self.xa.postal_codes_for(2, "C2"), (["2000", "2001"], 2))  # ambiguous
		self.assertEqual(self.xa.postal_codes_for(3, "D4"), (["4004"], 3))  # district-specific
		self.assertEqual(self.xa.postal_codes_for(2, "C3"), ([], None))  # unknown
		self.assertEqual(self.xa.postal_codes_for(9, "C1"), ([], None))
		self.assertTrue(self.xa.has_postal_codes)

	def test_broken_rows_are_skipped_not_fatal(self):
		xd = ds.get_dataset("xd", [TEST_ROOT])
		self.assertIsNotNone(xd)
		self.assertEqual([u.code for u in xd.options(1)], ["R1"])
		self.assertEqual([u.code for u in xd.options(2, "R1")], ["C1"])
		self.assertEqual(xd.postal_codes_for(2, "C1"), (["123"], 2))
		self.assertTrue(xd.warnings)

	def test_cache_reloads_when_files_change(self):
		tmp = tempfile.mkdtemp()
		try:
			shutil.copytree(os.path.join(TEST_ROOT, "xa"), os.path.join(tmp, "xa"))
			first = ds.get_dataset("xa", [tmp])
			self.assertIs(ds.get_dataset("xa", [tmp]), first)
			with open(os.path.join(tmp, "xa", "level1.csv"), "a", encoding="utf-8") as f:
				f.write("R4,New Region\n")
			os.utime(os.path.join(tmp, "xa", "level1.csv"), None)
			second = ds.get_dataset("xa", [tmp])
			self.assertIsNot(second, first)
			self.assertIsNotNone(second.get_unit(1, "R4"))
		finally:
			shutil.rmtree(tmp)
			ds.clear_cache()

	def test_safe_join_blocks_traversal(self):
		base = os.path.join(TEST_ROOT, "xa")
		self.assertIsNone(ds.safe_join(base, "../xb/manifest.json"))
		self.assertIsNone(ds.safe_join(base, "/etc/passwd"))
		self.assertIsNone(ds.safe_join(base, ""))
		self.assertTrue(ds.safe_join(base, "level1.csv").endswith("level1.csv"))

	def test_text_and_code_cleaning(self):
		self.assertEqual(ds.clean_text("  <b>Cebu</b>\tCity "), "bCebu/b City")
		self.assertEqual(ds.clean_code("AB-1.2_c"), "AB-1.2_c")
		self.assertEqual(ds.clean_code("A B"), "")
		self.assertEqual(ds.clean_code("A;B"), "")
		self.assertEqual(ds.normalize_name("  Ñuñoa  "), "nunoa")
		self.assertEqual(ds.normalize_country_code(" PH "), "ph")
		self.assertEqual(ds.normalize_country_code("phl"), "")


class TestShippedDatasets(unittest.TestCase):
	def test_every_shipped_dataset_loads(self):
		codes = ds.list_country_codes()
		self.assertIn("ph", codes)
		for code in codes:
			dataset = ds.get_dataset(code)
			self.assertIsNotNone(dataset, code)
			self.assertTrue(dataset.options(1), f"{code} has no top-level units")
			for lvl in dataset.levels:
				self.assertIn(lvl.target_field, ds.ALLOWED_TARGET_FIELDS)

	def test_philippines_hierarchy(self):
		ph = ds.get_dataset("ph")
		self.assertEqual([lvl.target_field for lvl in ph.levels], ["state", "city", "county"])
		cebu = ph.find_by_name(1, "Cebu")
		self.assertIsNotNone(cebu)
		cebu_city = ph.find_by_name(2, "city of cebu", cebu.code)
		self.assertIsNotNone(cebu_city)
		barangays = ph.options(3, cebu_city.code)
		self.assertGreater(len(barangays), 50)
		self.assertLess(len(barangays), 200)  # only one city's barangays, never the whole country
