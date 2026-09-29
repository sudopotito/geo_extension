# Copyright (c) 2025, sudo potito and contributors
# For license information, please see license.txt

"""
Country-agnostic geographic engine.

- ``dataset``  loads and indexes a country dataset (manifest + CSV files)
- ``validate`` checks a dataset before it is committed or shipped

Both modules work without a Frappe site so they can be used from tests,
CI and the ``bench geo-extension`` command.
"""
