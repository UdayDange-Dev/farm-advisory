frappe.query_reports["Basal Dose Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		  default: frappe.datetime.add_months(frappe.datetime.get_today(), -1) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "customer", label: __("Farmer (Customer)"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "taluka", label: __("Taluka"), fieldtype: "Link", options: "Farm Taluka" },
		{ fieldname: "crop", label: __("Crop"), fieldtype: "Link", options: "Farm Crop" },
	],
};
