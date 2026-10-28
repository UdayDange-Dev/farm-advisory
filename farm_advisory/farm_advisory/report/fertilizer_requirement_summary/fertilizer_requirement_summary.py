# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

"""Fertilizer quantities across recommendations — what to stock.

Grouped by fertilizer and pack size, the same key as each recommendation's
purchase list, so different packs are never merged: the combined purchase
view. With "Group by Crop" each crop's own rows are kept apart instead: the
crop-wise application view. Every fertilizer row belongs to exactly one crop
row, so neither view counts an amount twice.
"""

import frappe
from frappe import _
from frappe.utils import flt

COLUMNS = [
	("fertilizer_name", _("Fertilizer"), "Data", None, 220),
	("pack_kg", _("Pack (kg)"), "Float", None, 90),
	("recommendations", _("Recommendations"), "Int", None, 130),
	("qty_kg", _("Total Qty (kg)"), "Float", None, 120),
	("bags", _("Bags (sum of rows)"), "Float", None, 130),
	("amount", _("Amount"), "Currency", None, 130),
]
CROP_COLUMN = ("crop", _("Crop"), "Link", "Farm Crop", 120)


def execute(filters=None):
	filters = filters or {}
	cond = _conditions(filters)
	crop_rows = None
	if filters.get("crop"):
		# only the fertilizer rows of that crop, not the whole recommendation
		crop_rows = {
			(c.parent, c.crop_no)
			for c in frappe.get_all(
				"Basal Dose Crop",
				filters={"crop": filters["crop"], "parenttype": "Basal Dose Recommendation"},
				fields=["parent", "crop_no"],
			)
		}
		cond["name"] = ["in", list({p for p, _n in crop_rows}) or [""]]
	by_crop = bool(filters.get("group_by_crop"))
	columns = _columns([CROP_COLUMN, *COLUMNS] if by_crop else COLUMNS)
	names = frappe.get_list("Basal Dose Recommendation", filters=cond, pluck="name")
	if not names:
		return columns, []
	crop_of = {}
	if by_crop:
		crop_of = {
			(c.parent, c.crop_no): c.crop
			for c in frappe.get_all(
				"Basal Dose Crop",
				filters={"parent": ["in", names], "parenttype": "Basal Dose Recommendation"},
				fields=["parent", "crop_no", "crop"],
			)
		}
	row_filters = {"parent": ["in", names], "parenttype": "Basal Dose Recommendation"}
	if filters.get("fertilizer"):
		row_filters["fertilizer"] = filters["fertilizer"]
	groups = {}
	for r in frappe.get_all(
		"Basal Dose Fertilizer",
		filters=row_filters,
		fields=["parent", "crop_no", "fertilizer_name", "pack_kg", "qty_kg", "bags", "amount"],
	):
		if not r.fertilizer_name:
			continue
		if crop_rows is not None and (r.parent, r.crop_no) not in crop_rows:
			continue
		crop = crop_of.get((r.parent, r.crop_no), "") if by_crop else None
		key = (
			(r.fertilizer_name, flt(r.pack_kg)) if crop is None else (crop, r.fertilizer_name, flt(r.pack_kg))
		)
		g = groups.setdefault(
			key,
			{
				**({} if crop is None else {"crop": crop}),
				"fertilizer_name": r.fertilizer_name,
				"pack_kg": flt(r.pack_kg),
				"parents": set(),
				"qty_kg": 0,
				"bags": 0,
				"amount": 0,
			},
		)
		g["parents"].add(r.parent)
		for k in ("qty_kg", "bags", "amount"):
			g[k] += flt(r[k])
	rows = []
	for key in sorted(groups):
		g = groups[key]
		g["recommendations"] = len(g.pop("parents"))
		rows.append(g)
	return columns, rows


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
