frappe.query_reports["Crop Consultation Register"] = {
	filters: [
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date",
		  default: frappe.datetime.add_months(frappe.datetime.get_today(), -1) },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "village", label: __("Village"), fieldtype: "Link", options: "Farm Village" },
		{ fieldname: "district", label: __("District"), fieldtype: "Link", options: "Farm District" },
		{ fieldname: "crop", label: __("Crop"), fieldtype: "Link", options: "Farm Crop" },
		{ fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select",
		  options: "\nDraft\nAgronomist Approved\nIssued to Farmer" },
		{ fieldname: "max_severity", label: __("Highest Severity"), fieldtype: "Select",
		  options: "\nLow\nMedium\nHigh\nCritical" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "max_severity" && data && ["High", "Critical"].includes(data.max_severity)) {
			value = `<span style="color:var(--red-600);font-weight:600">${value}</span>`;
		}
		return value;
	},
};
