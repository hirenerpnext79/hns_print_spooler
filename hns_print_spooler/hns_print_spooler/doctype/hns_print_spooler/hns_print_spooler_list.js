frappe.listview_settings["HNS Print Spooler"] = {
	add_fields: ["status", "printer_name", "attachment_pdf", "site_name"],

	get_indicator: function(doc) {
		if (doc.status === "Printed") {
			return [__("Printed"), "green", "status,=,Printed"];
		} else if (doc.status === "Pending") {
			return [__("Pending"), "orange", "status,=,Pending"];
		} else if (doc.status === "Queued") {
			return [__("Queued"), "blue", "status,=,Queued"];
		} else if (doc.status === "Error") {
			return [__("Error"), "red", "status,=,Error"];
		}
		return [__(doc.status || "Pending"), "gray", "status,=," + doc.status];
	}
};
