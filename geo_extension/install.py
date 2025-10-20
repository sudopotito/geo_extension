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
    """Force fieldtypes to Autocomplete and set Re-ordering."""
    # 1) Fieldtypes → Autocomplete
    for fieldname in AC_FIELDS:
        _ensure_property(ADDRESS, fieldname, "fieldtype", "Autocomplete", "Data")

    # 2) Re-ordering
    _ensure_property(ADDRESS, "state", "insert_after", "address_line2", "Data")
    _ensure_property(ADDRESS, "county", "insert_after", "state", "Data")
    _ensure_property(ADDRESS, "city", "insert_after", "county", "Data")
    _ensure_property(ADDRESS, "barangay", "insert_after", "city", "Data")


def _ensure_property(
    doctype: str, fieldname: str, prop: str, value: str, property_type: str
):
    """
    Idempotently ensure a Property Setter (for a field) exists with the desired value.
    If one exists with a different value, update it.
    Skips creation if the field doesn't exist (standard or custom) to avoid junk setters.
    """
    # Verify field exists either as standard DocField or Custom Field
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
    if frappe.get_all(
        "DocField", filters={"parent": doctype, "fieldname": fieldname}, limit=1
    ):
        return True
    if frappe.get_all(
        "Custom Field", filters={"dt": doctype, "fieldname": fieldname}, limit=1
    ):
        return True
    return False
