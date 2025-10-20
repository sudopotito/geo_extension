# geo_extension/install.py
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

ADDRESS = "Address"
AC_FIELDS = [
    "city",
    "county",
    "state",
    "barangay",
]


def before_install():
    pass


def after_install(force: bool = False):
    setup_custom_fields(force)
    setup_property_setters()
    frappe.db.commit()


def setup_custom_fields(force: bool = False):
    """Create system-generated custom fields"""
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
    for fieldname in AC_FIELDS:
        _set_fieldtype_autocomplete(ADDRESS, fieldname)


def _set_fieldtype_autocomplete(doctype: str, fieldname: str):
    # Avoid duplicate PS entries for fieldtype
    ps = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": doctype,
            "field_name": fieldname,
            "property": "fieldtype",
        },
        fields=["name", "value"],
        limit=1,
    )

    if ps:
        # Update existing if needed
        if ps[0].value != "Autocomplete":
            doc = frappe.get_doc("Property Setter", ps[0].name)
            doc.value = "Autocomplete"
            doc.save(ignore_permissions=True)
        return

    # Create/overwrite property: property_type='Data' is correct for fieldtype props
    make_property_setter(
        doctype=doctype,
        fieldname=fieldname,
        property="fieldtype",
        value="Autocomplete",
        property_type="Data",
        for_doctype=False,
    )
