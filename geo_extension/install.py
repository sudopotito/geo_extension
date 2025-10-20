import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

ADDRESS = "Address"
AC_FIELDS = ["state", "county", "city", "barangay"]


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
    """Force fieldtypes to Autocomplete where applicable and set ordering."""
    # 1) Fieldtypes → Autocomplete (only touch fields that exist)
    for fieldname in AC_FIELDS:
        _ensure_property_if_exists(
            ADDRESS, fieldname, "fieldtype", "Autocomplete", "Data"
        )

    # 2) Re-ordering
    _ensure_property_if_exists(
        ADDRESS, "state", "insert_after", "address_line2", "Data"
    )
    _ensure_property_if_exists(ADDRESS, "county", "insert_after", "state", "Data")
    _ensure_property_if_exists(ADDRESS, "city", "insert_after", "county", "Data")
    _ensure_property_if_exists(ADDRESS, "barangay", "insert_after", "city", "Data")
    _ensure_property_if_exists(
        ADDRESS,
        "country",
        "insert_after",
        "barangay",
        "Data",
    )


def _ensure_property_if_exists(
    doctype: str, fieldname: str, prop: str, value: str, property_type: str
):
    """Create/update a Property Setter only if the target field exists."""
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
    """Return True if the field exists as a standard DocField or Custom Field."""
    return bool(
        frappe.get_all(
            "DocField", filters={"parent": doctype, "fieldname": fieldname}, limit=1
        )
        or frappe.get_all(
            "Custom Field", filters={"dt": doctype, "fieldname": fieldname}, limit=1
        )
    )
