frappe.provide("hns_print_spooler");

(function () {
	function load_qz_tray(callback) {
		if (window.qz) {
			callback();
			return;
		}
		let script = document.createElement("script");
		script.type = "text/javascript";
		script.src = "/assets/hns_print_spooler/js/qz-tray.min.js";
		script.onload = function () {
			callback();
		};
		script.onerror = function () {
			frappe.msgprint({
				title: __("QZ Tray Error"),
				indicator: "red",
				message: __("Failed to load local QZ Tray library.")
			});
		};
		document.head.appendChild(script);
	}

	function print_via_qz_tray(doctype, docname, print_format, copies, selected_printer, width_mm, height_mm, orientation, print_mode) {
		if (print_mode === "ZPL (Raw)") {
			frappe.call({
				method: "hns_print_spooler.api.get_zebra_design_zpl",
				args: {
					doctype: doctype,
					docname: docname,
					print_copies: copies || 1
				},
				freeze: true,
				freeze_message: __("Preparing ZPL for QZ Tray..."),
				callback: async function (r) {
					if (!r.message || !r.message.success) {
						frappe.msgprint({
							title: __("ZPL Generation Failed"),
							indicator: "red",
							message: (r.message && r.message.message) || __("Could not generate ZPL data.")
						});
						return;
					}

					try {
						if (!qz.websocket.isActive()) {
							await qz.websocket.connect();
						}

						let config = qz.configs.create(selected_printer, {
							copies: copies || 1,
							encoding: "UTF-8"
						});

						let printData = [{
							type: "raw",
							format: "command",
							flavor: "plain",
							data: r.message.zpl
						}];

						await qz.print(config, printData);

						frappe.show_alert({
							message: __("ZPL sent directly to printer via QZ Tray!"),
							indicator: "green"
						});
					} catch (err) {
						frappe.msgprint({
							title: __("QZ Tray Print Error"),
							indicator: "red",
							message: err && err.message ? err.message : String(err)
						});
					}
				}
			});
			return;
		}

		frappe.call({
			method: "hns_print_spooler.api.get_print_html",
			args: {
				doctype: doctype,
				docname: docname,
				print_format: print_format || ""
			},
			freeze: true,
			freeze_message: __("Preparing HTML for QZ Tray..."),
			callback: async function (r) {
				if (!r.message || !r.message.success) {
					frappe.msgprint({
						title: __("HTML Generation Failed"),
						indicator: "red",
						message: (r.message && r.message.message) || __("Could not fetch print HTML.")
					});
					return;
				}

				let html_data = r.message.html;

				try {
					if (!qz.websocket.isActive()) {
						await qz.websocket.connect();
					}

					let w_num = parseFloat(String(width_mm || "37").replace(/[^\d.]/g, "")) || 37;
					let h_num = parseFloat(String(height_mm || "25").replace(/[^\d.]/g, "")) || 25;

					let config = qz.configs.create(selected_printer, {
						copies: copies || 1,
						units: "mm",
						size: { width: w_num, height: h_num },
						margins: 0,
						scaleContent: true
					});

					let printData = [{
						type: "pixel",
						format: "html",
						flavor: "plain",
						data: html_data
					}];

					await qz.print(config, printData);

					frappe.show_alert({
						message: __("HTML sent directly to printer via QZ Tray!"),
						indicator: "green"
					});
				} catch (err) {
					frappe.msgprint({
						title: __("QZ Tray Print Error"),
						indicator: "red",
						message: err && err.message ? err.message : String(err)
					});
				}
			}
		});
	}

	hns_print_spooler.open_browser_print_popup = function (doctype, docname, print_format) {
		let url = frappe.urllib.get_full_url(
			"/printview?doctype=" + encodeURIComponent(doctype) +
			"&name=" + encodeURIComponent(docname) +
			"&trigger_print=1" +
			(print_format ? "&format=" + encodeURIComponent(print_format) : "")
		);
		let print_window = window.open(url, "_blank");
		if (print_window) {
			print_window.focus();
		}
	};

	function add_action_buttons() {
		let route = frappe.get_route();
		if (!route || route[0] !== "print") return;

		let doctype = route[1];
		let docname = route.slice(2).join("/");
		if (!doctype || !docname) return;

		let page = (frappe.pages && frappe.pages["print"] && frappe.pages["print"].page)
			|| (cur_page ? cur_page.page : null);
		if (!page || !page.wrapper) return;

		let doc = frappe.get_doc(doctype, docname);
		let default_ip = (doc && doc.printer_name) || "192.168.0.182";

		// 0. "Print (No Popup)" Button (Direct Silent Printing to Printer)
		if (
			page.wrapper.find(".btn-browser-print-popup, .btn-direct-silent-print").length === 0 &&
			page.wrapper.find('button:contains("Print (No Popup)"), button:contains("Print (Browser Popup)")').length === 0
		) {
			let btn_direct = page.add_button(__("Print (No Popup)"), function () {
				let format_input = page.wrapper.find('input[data-fieldname="print_format"]');
				let selected_format = format_input.length ? format_input.val() : "";

				let copies_input = page.wrapper.find('input[data-fieldname="print_copies"]');
				let copies = copies_input.length ? parseInt(copies_input.val()) || 1 : 1;

				frappe.show_alert({
					message: __("Sending silent print job..."),
					indicator: "blue"
				});

				frappe.call({
					method: "hns_print_spooler.api.direct_silent_print",
					args: {
						doctype: doctype,
						docname: docname,
						print_format: selected_format || "",
						ip_address: default_ip,
						print_copies: copies
					},
					freeze: true,
					freeze_message: __("Printing silently to {0}...", [default_ip]),
					callback: function (r) {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: r.message.message,
								indicator: "green"
							});
						} else {
							frappe.msgprint({
								title: __("Print Failed"),
								indicator: "red",
								message: (r.message && r.message.message) || __("Silent printing failed.")
							});
						}
					}
				});
			}, { icon: "printer" });

			if (btn_direct) {
				btn_direct.addClass("btn-direct-silent-print btn-primary");
			}
		}

		// 1. Existing "Print to IP" Button (Remains exactly as requested)
		if (
			page.wrapper.find(".btn-print-to-ip").length === 0 &&
			page.wrapper.find('button:contains("Print to IP")').length === 0
		) {
			let btn_ip = page.add_button(__("Print to IP"), function () {
				let format_input = page.wrapper.find('input[data-fieldname="print_format"]');
				let selected_format = format_input.length ? format_input.val() : "";

				let default_w = "37mm";
				let default_h = "25mm";
				let default_ori = "Landscape";
				if (selected_format && selected_format.toLowerCase().includes("37 x 25")) {
					default_w = "37mm";
					default_h = "25mm";
					default_ori = "Landscape";
				}

				frappe.prompt([
					{
						fieldname: "ip_address",
						label: __("Printer IP Address"),
						fieldtype: "Data",
						default: default_ip,
						reqd: 1
					},
					{
						fieldname: "print_format",
						label: __("Print Format"),
						fieldtype: "Link",
						options: "Print Format",
						default: selected_format,
						get_query: () => ({ filters: { doc_type: doctype } }),
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
						default: default_w
					},
					{
						fieldtype: "Column Break"
					},
					{
						fieldname: "page_height",
						label: __("Height (e.g. 37mm, 25mm)"),
						fieldtype: "Data",
						default: default_h
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
						default: default_ori
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
				], function (values) {
					frappe.call({
						method: "hns_print_spooler.api.print_doc_format_to_ip",
						args: {
							doctype: doctype,
							docname: docname,
							ip_address: values.ip_address,
							print_format: values.print_format || selected_format || "",
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
						callback: function (r) {
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
			}, { icon: "printer" });

			if (btn_ip) {
				btn_ip.addClass("btn-print-to-ip");
			}
		}

		// 2. New "Print Zebra Design" Button (Runs native Zebra Designer code to IP only)
		if (
			page.wrapper.find(".btn-print-zebra-design").length === 0 &&
			page.wrapper.find('button:contains("Print Zebra Design")').length === 0
		) {
			let btn_zebra = page.add_button(__("Print Zebra Design"), function () {
				frappe.prompt([
					{
						fieldname: "ip_address",
						label: __("Zebra Printer IP"),
						fieldtype: "Data",
						default: default_ip,
						reqd: 1
					},
					{
						fieldname: "print_copies",
						label: __("Print Copies"),
						fieldtype: "Int",
						default: 1
					}
				], function (values) {
					frappe.call({
						method: "hns_print_spooler.api.print_zebra_design_to_ip",
						args: {
							doctype: doctype,
							docname: docname,
							ip_address: values.ip_address,
							print_copies: values.print_copies || 1
						},
						freeze: true,
						freeze_message: __("Sending Native Zebra Design to Printer..."),
						callback: function (r) {
							if (r.message && r.message.success) {
								frappe.show_alert({
									message: r.message.message,
									indicator: "green"
								});
							} else {
								frappe.msgprint({
									title: __("Zebra Print Failed"),
									indicator: "red",
									message: (r.message && r.message.message) || __("Printing failed.")
								});
							}
						}
					});
				}, __("Print Native Zebra Design"), __("Print ZPL"));
			}, { icon: "tag" });

			if (btn_zebra) {
				btn_zebra.addClass("btn-print-zebra-design");
			}
		}

		// 3. New "Print via QZ Tray" Button (Client-side raw printer connection)
		if (
			page.wrapper.find(".btn-print-qz-tray").length === 0 &&
			page.wrapper.find('button:contains("Print via QZ Tray")').length === 0
		) {
			let btn_qz = page.add_button(__("Print via QZ Tray"), function () {
				load_qz_tray(async function () {
					try {
						if (!qz.websocket.isActive()) {
							await qz.websocket.connect();
						}

						let printer_list = [];
						try {
							printer_list = await qz.printers.find();
						} catch (e) {
							printer_list = [];
						}

						let default_prn = printer_list.length > 0 ? printer_list[0] : "";
						let zebra_match = printer_list.find(p => p.toLowerCase().includes("zebra") || p.toLowerCase().includes("zdesigner") || p.toLowerCase().includes("barcode") || p.toLowerCase().includes("label"));
						if (zebra_match) default_prn = zebra_match;

						let format_input = page.wrapper.find('input[data-fieldname="print_format"]');
						let selected_format = format_input.length ? format_input.val() : "";

						frappe.prompt([
							{
								fieldname: "printer_name",
								label: __("Select Local / Network Printer"),
								fieldtype: printer_list.length ? "Select" : "Data",
								options: printer_list.length ? printer_list : undefined,
								default: default_prn,
								reqd: 1
							},
							{
								fieldname: "print_mode",
								label: __("Print Mode"),
								fieldtype: "Select",
								options: ["HTML (Direct)", "ZPL (Raw)"],
								default: "HTML (Direct)",
								reqd: 1
							},
							{
								fieldname: "print_format",
								label: __("Print Format"),
								fieldtype: "Link",
								options: "Print Format",
								default: selected_format,
								get_query: () => ({ filters: { doc_type: doctype } }),
								reqd: 0
							},
							{
								fieldname: "page_width",
								label: __("Width (e.g. 37mm)"),
								fieldtype: "Data",
								default: "37mm"
							},
							{
								fieldname: "page_height",
								label: __("Height (e.g. 25mm)"),
								fieldtype: "Data",
								default: "25mm"
							},
							{
								fieldname: "orientation",
								label: __("Orientation"),
								fieldtype: "Select",
								options: ["Landscape", "Portrait"],
								default: "Landscape"
							},
							{
								fieldname: "print_copies",
								label: __("Print Copies"),
								fieldtype: "Int",
								default: 1
							}
						], function (values) {
							print_via_qz_tray(
								doctype,
								docname,
								values.print_format || selected_format || "",
								values.print_copies || 1,
								values.printer_name,
								values.page_width || "37mm",
								values.page_height || "25mm",
								values.orientation || "Landscape",
								values.print_mode || "HTML (Direct)"
							);
						}, __("QZ Tray Print"), __("Print"));

					} catch (conn_err) {
						frappe.msgprint({
							title: __("QZ Tray Not Connected"),
							indicator: "orange",
							message: __("QZ Tray is not running on your computer. Please make sure QZ Tray application is launched and running, then try again.")
						});
					}
				});
			}, { icon: "server" });

			if (btn_qz) {
				btn_qz.addClass("btn-print-qz-tray");
			}
		}
	}

	$(document).on("page-change", function () {
		setTimeout(add_action_buttons, 300);
	});

	if (frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			setTimeout(add_action_buttons, 300);
		});
	}
})();
