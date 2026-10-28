# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

from collections import Counter

import frappe
from frappe import _

COLUMNS = [
	("name", _("Schedule"), "Link", "Spray Schedule", 140),
	("posting_date", _("Date"), "Date", None, 95),
	("farmer_name", _("Farmer"), "Data", None, 170),
	("customer", _("Customer"), "Link", "Customer", 130),
	("mobile_no", _("Mobile"), "Data", None, 105),
	("village", _("Village"), "Link", "Farm Village", 110),
	("taluka", _("Taluka"), "Link", "Farm Taluka", 100),
	("branch", _("Branch"), "Link", "Branch", 140),
	("crop", _("Crop"), "Link", "Farm Crop", 100),
	("plant_count", _("Plants"), "Int", None, 80),
	("total_water", _("Water (L)"), "Float", None, 90),
	("sprays", _("Sprays"), "Int", None, 70),
	("grand_total", _("Total"), "Currency", None, 110),
	("grand_pack_total", _("Value at Full Packs"), "Currency", None, 130),
]


def execute(filters=None):
	filters = filters or {}
	fields = [c[0] for c in COLUMNS if c[0] != "sprays"]
	data = frappe.get_list(
		"Spray Schedule",
		filters=_conditions(filters, ("branch", "crop")),
		fields=fields,
		order_by="posting_date desc, creation desc",
	)
	if data:
		counts = Counter(
			frappe.get_all(
				"Spray Schedule Spray", filters={"parent": ["in", [d.name for d in data]]}, pluck="parent"
			)
		)
		for d in data:
			d["sprays"] = counts.get(d.name, 0)
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
