frappe.listview_settings["Crop Consultation"] = {
	add_fields: ["status", "max_severity"],
	get_indicator(doc) {
		if (doc.status === "Issued to Farmer") return [__("Issued to Farmer"), "green", "status,=,Issued to Farmer"];
		if (doc.status === "Agronomist Approved") return [__("Agronomist Approved"), "blue", "status,=,Agronomist Approved"];
		if (["High", "Critical"].includes(doc.max_severity)) return [__("Draft – {0}", [__(doc.max_severity)]), "red", "status,=,Draft"];
		return [__("Draft"), "orange", "status,=,Draft"];
	},
};
