# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""Tests for the dataset validator. No site required."""

import contextlib
import io
import os
import unittest

from geo_extension.geo import validate as v

TEST_ROOT = os.path.join(os.path.dirname(__file__), "data", "countries")
TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "template", "xx")


def messages(report, severity=None):
	return [i.message for i in report.issues if severity is None or i.severity == severity]


class TestValidator(unittest.TestCase):
	def test_valid_dataset_passes(self):
		report = v.validate_path(os.path.join(TEST_ROOT, "xa"))
		self.assertTrue(report.ok, messages(report))
		self.assertEqual(report.counts, [3, 4, 4])
		self.assertEqual(report.postal_count, 4)
		# partial coverage is reported, but only as a warning
		self.assertTrue(any("no children" in m for m in messages(report, v.WARNING)))

	def test_template_passes(self):
		report = v.validate_path(TEMPLATE)
		self.assertTrue(report.ok, messages(report))
		self.assertEqual(report.counts, [3, 6, 8])

	def test_missing_directory(self):
		report = v.validate_path(os.path.join(TEST_ROOT, "zz"))
		self.assertFalse(report.ok)

	def test_malformed_manifest(self):
		report = v.validate_path(os.path.join(TEST_ROOT, "xb"))
		self.assertFalse(report.ok)
		self.assertEqual(len(report.errors), 1)
		self.assertEqual(report.errors[0].file, "manifest.json")

	def test_invalid_target_field(self):
		report = v.validate_path(os.path.join(TEST_ROOT, "xc"))
		self.assertFalse(report.ok)
		self.assertTrue(any("target_field 'region'" in m for m in messages(report, v.ERROR)))

	def test_broken_dataset_reports_every_problem(self):
		report = v.validate_path(os.path.join(TEST_ROOT, "xd"))
		self.assertFalse(report.ok)
		errors = messages(report, v.ERROR)
		warnings = messages(report, v.WARNING)
		expected_errors = [
			"duplicate code 'R1'",
			"missing name for code 'R2'",
			"invalid code 'R 3'",
			"parent_code 'R9' not found in level1.csv",
			"'C3' references itself as parent",
			"postal code '12345' does not match pattern",
			"level 5 does not exist",
			"code 'C9' not found in level2.csv",
		]
		for expected in expected_errors:
			self.assertTrue(any(expected in e for e in errors), f"missing error: {expected}\n{errors}")
		self.assertTrue(any("'parent_level' is obsolete" in w for w in warnings))
		self.assertTrue(any("missing recommended property 'source'" in w for w in warnings))
		# line numbers point at the offending CSV row (header is line 1)
		dup = next(i for i in report.errors if "duplicate code 'R1'" in i.message)
		self.assertEqual((dup.file, dup.line), ("level1.csv", 3))

	def test_unknown_country_code_is_error_only_for_shipped_datasets(self):
		lenient = v.validate_path(os.path.join(TEST_ROOT, "xa"))
		self.assertTrue(any("not a country code known" in m for m in messages(lenient, v.WARNING)))
		strict = v.validate_path(os.path.join(TEST_ROOT, "xa"), require_known_country=True)
		self.assertFalse(strict.ok)

	def test_shipped_datasets_are_valid(self):
		reports = v.validate_all()
		self.assertGreaterEqual(len(reports), 7)
		for report in reports:
			self.assertTrue(report.ok, v.format_report(report))

	def test_cli_exit_codes(self):
		def run(*argv):
			with contextlib.redirect_stdout(io.StringIO()) as out:
				code = v.main(list(argv))
			return code, out.getvalue()

		self.assertEqual(run("--quiet")[0], 0)
		self.assertEqual(run("--path", os.path.join(TEST_ROOT, "xd"), "--quiet")[0], 1)
		self.assertEqual(run("--path", os.path.join(TEST_ROOT, "xa"), "--quiet", "--strict")[0], 1)
		code, output = run("zz")
		self.assertEqual(code, 1)
		self.assertIn("no dataset found", output)
		self.assertNotIn("no dataset found", run("zz", "--quiet")[1])
