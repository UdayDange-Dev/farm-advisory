# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _

COLUMNS = [
	("name", _("Recommendation"), "Link", "Basal Dose Recommendation", 150),
	("posting_date", _("Date"), "Date", None, 95),
	("farmer_name", _("Farmer"), "Data", None, 170),
	("customer", _("Customer"), "Link", "Customer", 130),
	("mobile_no", _("Mobile"), "Data", None, 105),
	("village", _("Village"), "Link", "Farm Village", 110),
	("taluka", _("Taluka"), "Link", "Farm Taluka", 100),
	("crops", _("Crops"), "Data", None, 180),
	("total_plants", _("Plants"), "Float", None, 90),
	("total_qty_kg", _("Fertilizer (kg)"), "Float", None, 110),
	("grand_total", _("Total"), "Currency", None, 120),
]


def execute(filters=None):
	filters = filters or {}
	cond = _conditions(filters)
	if filters.get("crop"):
		parents = frappe.get_all(
			"Basal Dose Crop",
			filters={"crop": filters["crop"], "parenttype": "Basal Dose Recommendation"},
			pluck="parent",
		)
		cond["name"] = ["in", parents or [""]]
	fields = [c[0] for c in COLUMNS if c[0] != "crops"]
	data = frappe.get_list(
		"Basal Dose Recommendation", filters=cond, fields=fields, order_by="posting_date desc, creation desc"
	)
	if data:
		crops = {}
		for row in frappe.get_all(
			"Basal Dose Crop",
			filters={"parent": ["in", [d.name for d in data]]},
			fields=["parent", "crop"],
			order_by="idx asc",
		):
			crops.setdefault(row.parent, []).append(row.crop)
		for d in data:
			d["crops"] = ", ".join(crops.get(d.name, []))
	return _columns(COLUMNS), data


def _conditions(filters, extra=()):
	cond = {}
	if filters.get("from_date") and filters.get("to_date"):
		cond["posting_date"] = ["between", (filters["from_date"], filters["to_date"])]
	for key in ("customer", "taluka", *extra):
		if filters.get(key):
			cond[key] = filters[key]
	return cond


def _columns(spec):
	return [{"fieldname": f, "label": l, "fieldtype": t, "options": o, "width": w} for f, l, t, o, w in spec]
