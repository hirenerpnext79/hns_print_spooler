frappe.ui.form.on("HNS Print Spooler", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Print"), function() {
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
		}
	}
});
