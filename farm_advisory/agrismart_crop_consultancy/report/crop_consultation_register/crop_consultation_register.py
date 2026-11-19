# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

"""Visit history: one row per Crop Consultation (the prototype's "Records" tab)."""

import frappe
from frappe import _

COLUMNS = [
	("name", _("Consultation"), "Link", "Crop Consultation", 150),
	("visit_date", _("Visit Date"), "Date", None, 95),
	("farmer_name", _("Farmer"), "Data", None, 170),
	("customer", _("Customer"), "Link", "Customer", 130),
	("mobile_no", _("Mobile"), "Data", None, 105),
	("village", _("Village"), "Link", "Farm Village", 110),
	("district", _("District"), "Link", "Farm District", 110),
	("crop_summary", _("Crops"), "Data", None, 170),
	("crop_area_total", _("Crop Area (acre)"), "Float", None, 110),
	("total_plants", _("Plants"), "Int", None, 90),
	("problem_count", _("Cases"), "Int", None, 70),
	("max_severity", _("Highest Severity"), "Data", None, 110),
	("ndvi_status", _("Crop Health"), "Data", None, 130),
	("status", _("Status"), "Data", None, 140),
	("agronomist", _("Agronomist"), "Data", None, 130),
	("next_visit", _("Next Visit"), "Date", None, 95),
]
FILTER_FIELDS = ("customer", "village", "district", "status", "max_severity", "branch")


def execute(filters=None):
	filters = filters or {}
	cond = {}
	if filters.get("from_date") and filters.get("to_date"):
		cond["visit_date"] = ["between", (filters["from_date"], filters["to_date"])]
	for key in FILTER_FIELDS:
		if filters.get(key):
			cond[key] = filters[key]
	if filters.get("crop"):
		parents = frappe.get_all(
			"Crop Consultation Block",
			filters={"crop": filters["crop"], "parenttype": "Crop Consultation"},
			pluck="parent",
		)
		cond["name"] = ["in", parents or [""]]
	data = frappe.get_list(
		"Crop Consultation",
		filters=cond,
		fields=[c[0] for c in COLUMNS],
		order_by="visit_date desc, creation desc",
	)
	columns = [
		{"fieldname": f, "label": l, "fieldtype": t, "options": o, "width": w} for f, l, t, o, w in COLUMNS
	]
	return columns, data
