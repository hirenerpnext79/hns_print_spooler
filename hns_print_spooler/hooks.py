app_name = "hns_print_spooler"
app_title = "Hns Print Spooler"
app_publisher = "Hns Print Spooler"
app_description = "Hns Print Spooler"
app_email = "hns@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "hns_print_spooler",
# 		"logo": "/assets/hns_print_spooler/logo.png",
# 		"title": "Hns Print Spooler",
# 		"route": "/hns_print_spooler",
# 		"has_permission": "hns_print_spooler.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/hns_print_spooler/css/hns_print_spooler.css"
# app_include_js = []

# include js, css files in header of web template
# web_include_css = "/assets/hns_print_spooler/css/hns_print_spooler.css"
# web_include_js = "/assets/hns_print_spooler/js/hns_print_spooler.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hns_print_spooler/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"HNS Print Spooler": "hns_print_spooler/doctype/hns_print_spooler/hns_print_spooler.js",
}
doctype_list_js = {
	"HNS Print Spooler": "hns_print_spooler/doctype/hns_print_spooler/hns_print_spooler_list.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hns_print_spooler/public/icons.svg"

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
# 	"methods": "hns_print_spooler.utils.jinja_methods",
# 	"filters": "hns_print_spooler.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "hns_print_spooler.install.before_install"
# after_install = "hns_print_spooler.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "hns_print_spooler.uninstall.before_uninstall"
# after_uninstall = "hns_print_spooler.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hns_print_spooler.utils.before_app_install"
# after_app_install = "hns_print_spooler.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hns_print_spooler.utils.before_app_uninstall"
# after_app_uninstall = "hns_print_spooler.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hns_print_spooler.notifications.get_notification_config"

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
# 		"hns_print_spooler.tasks.all"
# 	],
# 	"daily": [
# 		"hns_print_spooler.tasks.daily"
# 	],
# 	"hourly": [
# 		"hns_print_spooler.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hns_print_spooler.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hns_print_spooler.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "hns_print_spooler.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hns_print_spooler.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hns_print_spooler.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hns_print_spooler.utils.before_request"]
# after_request = ["hns_print_spooler.utils.after_request"]

# Job Events
# ----------
# before_job = ["hns_print_spooler.utils.before_job"]
# after_job = ["hns_print_spooler.utils.after_job"]

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
# 	"hns_print_spooler.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

