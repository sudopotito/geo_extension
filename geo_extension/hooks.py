app_name = "geo_extension"
app_title = "Geo Extension"
app_publisher = "sudo potito"
app_description = "Enhancing the Address Experience in Frappe"
app_email = "sudopotito@gmail.com"
app_license = "GPL-3.0"

# Desk assets
# -----------
# geo_selector.js: reusable cascading selector (frappe.geo_extension)
# quick_entry.js: adds it to quick-entry dialogs that contain address fields
app_include_js = ["/assets/geo_extension/js/geo_selector.js", "/assets/geo_extension/js/quick_entry.js"]

# address.js wires the selector (loaded globally above) to the Address form
doctype_js = {"Address": "public/js/address.js"}

# Website: standard Web Forms on Address (e.g. ERPNext's portal /address) get the
# selector too. The files are inlined into the web form page, so both are listed.
webform_include_js = {"Address": ["public/js/geo_selector.js", "public/js/address_web_form.js"]}

# Install / migrate / uninstall
# -----------------------------
# geo_extension makes no schema or layout changes to Address. These hooks only
# remove customizations left behind by versions <= 1.4 (see install.py).
after_install = "geo_extension.install.after_install"
after_migrate = "geo_extension.install.after_migrate"
before_uninstall = "geo_extension.install.before_uninstall"
