"""Register the Agrismart Crop Consultancy module before its DocTypes are synced."""

import frappe


def execute():
	if not frappe.db.exists("Module Def", "Agrismart Crop Consultancy"):
		frappe.get_doc(
			{
				"doctype": "Module Def",
				"module_name": "Agrismart Crop Consultancy",
				"app_name": "farm_advisory",
			}
		).insert(ignore_permissions=True)
