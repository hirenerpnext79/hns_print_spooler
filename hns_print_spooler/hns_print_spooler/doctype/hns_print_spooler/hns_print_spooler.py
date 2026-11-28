# Copyright (c) 2026, Hns Print Spooler and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from hns_print_spooler.api import auto_print_on_save, _is_ip_printer


class HNSPrintSpooler(Document):
	def after_insert(self):
		try:
			if self.printer_name and _is_ip_printer(self.printer_name) and self.status == "Pending":
				auto_print_on_save(self.doctype, self.name, self.printer_name)
		except Exception as e:
			frappe.log_error(title="Auto Print After Insert Error", message=str(e))
