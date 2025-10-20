import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def before_install():
    pass


def after_install(force: bool = False):
    setup_custom_fields(force)
    frappe.db.commit()


def setup_custom_fields(force: bool = False):
    """Create system-generated custom fields"""

    custom_fields = {
        "Address": [
            {
                "fieldname": "barangay",
                "label": "Barangay",
                "fieldtype": "Data",
                "insert_after": "city",
            }
        ]
    }

    create_custom_fields(custom_fields, ignore_validate=True, update=True)
