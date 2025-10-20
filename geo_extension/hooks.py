app_name = "geo_extension"
app_title = "Geo Extension"
app_publisher = "sudo potito"
app_description = "Fee"
app_email = "sudopotito@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "geo_extension",
# 		"logo": "/assets/geo_extension/logo.png",
# 		"title": "Geo Extension",
# 		"route": "/geo_extension",
# 		"has_permission": "geo_extension.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/geo_extension/css/geo_extension.css"
# app_include_js = "/assets/geo_extension/js/geo_extension.js"

# include js, css files in header of web template
# web_include_css = "/assets/geo_extension/css/geo_extension.css"
# web_include_js = "/assets/geo_extension/js/geo_extension.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "geo_extension/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "geo_extension/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "geo_extension.utils.jinja_methods",
# 	"filters": "geo_extension.utils.jinja_filters"
# }

# Installation
# ------------

before_install = "geo_extension.install.before_install"
after_install = "geo_extension.install.after_install"


# Migration
# ------------

after_migrate = "geo_extension.install.after_install"


# Uninstallation
# ------------

# before_uninstall = "geo_extension.uninstall.before_uninstall"
# after_uninstall = "geo_extension.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "geo_extension.utils.before_app_install"
# after_app_install = "geo_extension.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "geo_extension.utils.before_app_uninstall"
# after_app_uninstall = "geo_extension.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "geo_extension.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"geo_extension.tasks.all"
# 	],
# 	"daily": [
# 		"geo_extension.tasks.daily"
# 	],
# 	"hourly": [
# 		"geo_extension.tasks.hourly"
# 	],
# 	"weekly": [
# 		"geo_extension.tasks.weekly"
# 	],
# 	"monthly": [
# 		"geo_extension.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "geo_extension.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "geo_extension.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "geo_extension.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["geo_extension.utils.before_request"]
# after_request = ["geo_extension.utils.after_request"]

# Job Events
# ----------
# before_job = ["geo_extension.utils.before_job"]
# after_job = ["geo_extension.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"geo_extension.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
