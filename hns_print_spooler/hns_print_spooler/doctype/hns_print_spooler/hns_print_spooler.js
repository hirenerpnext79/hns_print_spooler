frappe.ui.form.on("HNS Print Spooler", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Print (No Popup)"), function() {
				frappe.call({
					method: "hns_print_spooler.api.direct_silent_print",
					args: {
						doctype: frm.doctype,
						docname: frm.doc.name,
						ip_address: frm.doc.printer_name || "192.168.0.182",
						print_copies: 1
					},
					freeze: true,
					freeze_message: __("Printing silently..."),
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: r.message.message,
								indicator: "green"
							});
							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: __("Print Failed"),
								indicator: "red",
								message: (r.message && r.message.message) || __("Printing failed.")
							});
						}
					}
				});
			}).addClass("btn-primary");

			frm.add_custom_button(__("Direct Print"), function() {
				frappe.call({
					method: "hns_print_spooler.api.print_job_direct",
					args: {
						job_name: frm.doc.name
					},
					freeze: true,
					freeze_message: __("Sending print job to printer..."),
					callback: function(r) {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: r.message.message,
								indicator: "green"
							});
							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: __("Print Failed"),
								indicator: "red",
								message: (r.message && r.message.message) || __("Printing failed.")
							});
						}
					}
				});
			});

			frm.add_custom_button(__("Print Format to IP"), function() {
				frappe.prompt([
					{
						fieldname: "ip_address",
						label: __("Printer IP Address"),
						fieldtype: "Data",
						default: frm.doc.printer_name || "192.168.0.182",
						reqd: 1
					},
					{
						fieldname: "print_format",
						label: __("Print Format"),
						fieldtype: "Link",
						options: "Print Format",
						get_query: () => ({ filters: { doc_type: frm.doctype } }),
						reqd: 0
					},
					{
						fieldtype: "Section Break",
						label: __("Label Dimensions")
					},
					{
						fieldname: "page_width",
						label: __("Width (e.g. 25mm, 37mm)"),
						fieldtype: "Data",
						default: "25mm"
					},
					{
						fieldtype: "Column Break"
					},
					{
						fieldname: "page_height",
						label: __("Height (e.g. 37mm, 25mm)"),
						fieldtype: "Data",
						default: "37mm"
					},
					{
						fieldtype: "Section Break",
						label: __("Margins (Padding)")
					},
					{
						fieldname: "margin_top",
						label: __("Margin Top (e.g. 0mm)"),
						fieldtype: "Data",
						default: "0mm"
					},
					{
						fieldname: "margin_bottom",
						label: __("Margin Bottom (e.g. 0mm)"),
						fieldtype: "Data",
						default: "0mm"
					},
					{
						fieldtype: "Column Break"
					},
					{
						fieldname: "margin_left",
						label: __("Margin Left (e.g. 0mm)"),
						fieldtype: "Data",
						default: "0mm"
					},
					{
						fieldname: "margin_right",
						label: __("Margin Right (e.g. 0mm)"),
						fieldtype: "Data",
						default: "0mm"
					},
					{
						fieldtype: "Section Break",
						label: __("Print Options")
					},
					{
						fieldname: "orientation",
						label: __("Orientation"),
						fieldtype: "Select",
						options: ["Portrait", "Landscape"],
						default: "Portrait"
					},
					{
						fieldtype: "Column Break"
					},
					{
						fieldname: "print_copies",
						label: __("Print Copies"),
						fieldtype: "Int",
						default: 1
					}
				], function(values) {
					frappe.call({
						method: "hns_print_spooler.api.print_doc_format_to_ip",
						args: {
							doctype: frm.doctype,
							docname: frm.doc.name,
							ip_address: values.ip_address,
							print_format: values.print_format || "",
							page_width: values.page_width || "",
							page_height: values.page_height || "",
							margin_top: values.margin_top || "0mm",
							margin_bottom: values.margin_bottom || "0mm",
							margin_left: values.margin_left || "0mm",
							margin_right: values.margin_right || "0mm",
							orientation: values.orientation || "Portrait",
							print_copies: values.print_copies || 1
						},
						freeze: true,
						freeze_message: __("Sending Print Format to IP Printer..."),
						callback: function(r) {
							if (r.message && r.message.success) {
								frappe.show_alert({
									message: r.message.message,
									indicator: "green"
								});
							} else {
								frappe.msgprint({
									title: __("Print Failed"),
									indicator: "red",
									message: (r.message && r.message.message) || __("Printing failed.")
								});
							}
						}
					});
				}, __("Print Format to IP"), __("Print"));
			});
		}
	}
});
