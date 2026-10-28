# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

"""Data for the Basal Dose page: summary figures and crop-wise lists.

Read-only. Every query on Basal Dose Recommendation goes through
``frappe.get_list``, so the figures are limited to records the user may read
(role permissions, user permissions and sharing). Child rows are fetched only
for parents that query has already returned.

A recommendation can hold several crops (``Basal Dose Crop`` rows), so a
recommendation with Banana and Mango is counted, and listed, under both.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_first_day, get_last_day, getdate, today

from farm_advisory.farm_advisory.report.fertilizer_requirement_summary import fertilizer_requirement_summary
from farm_advisory.utils.numbers import fmt, inr0

BASAL = "Basal Dose Recommendation"
# The page's tabs, in order. These are the stored Farm Crop names, shown as-is.
CROP_TABS = ("Pomegranate", "Banana", "Guava", "Mango", "Papaya")
MAX_PAGE_LENGTH = 100
RECENT = 5
TOP_FERTILIZERS = 6


def _check_read():
	frappe.has_permission(BASAL, "read", throw=True)


def _crop_counts():
	"""Recommendations per crop, each recommendation once per crop."""
	pairs = frappe.get_list(
		BASAL,
		filters={"crops.crop": ["in", CROP_TABS]},
		fields=["name", "crops.crop"],
		distinct=True,
	)
	counts = defaultdict(int)
	for p in pairs:
		counts[p.crop] += 1
	return counts


@frappe.whitelist()
def get_overview():
	_check_read()
	agg = frappe.get_list(
		BASAL,
		fields=[
			{"COUNT": "*", "as": "count"},
			{"SUM": "total_plants", "as": "plants"},
			{"SUM": "total_qty_kg", "as": "qty_kg"},
			{"SUM": "grand_total", "as": "amount"},
		],
	)[0]
	this_month = frappe.get_list(
		BASAL,
		filters={"posting_date": ["between", [get_first_day(today()), get_last_day(today())]]},
		fields=[{"COUNT": "*", "as": "count"}],
	)[0]

	crops = set(frappe.get_all("Farm Crop", filters={"name": ["in", CROP_TABS]}, pluck="name"))
	with_template = set(
		frappe.get_all(
			"Farm Crop Fertilizer Template",
			filters={"parent": ["in", CROP_TABS], "parenttype": "Farm Crop"},
			pluck="parent",
		)
	)
	counts = _crop_counts()
	tabs = [
		{
			"crop": name,
			"exists": name in crops,
			"has_template": name in with_template,
			"count": counts.get(name, 0),
		}
		for name in CROP_TABS
	]

	recent = frappe.get_list(
		BASAL,
		fields=["name", "posting_date", "farmer_name", "customer", "grand_total"],
		order_by="posting_date desc, creation desc",
		limit=RECENT,
	)
	recent_crops = _crop_names_of([r.name for r in recent])
	for r in recent:
		r["crops"] = ", ".join(recent_crops.get(r.name, []))
		r["date"] = frappe.format(r.posting_date, {"fieldtype": "Date"})
		r["amount"] = inr0(r.pop("grand_total"))

	# the Fertilizer Requirement Summary report itself, so the two never disagree
	_cols, fert_rows = fertilizer_requirement_summary.execute({})
	fert_rows = sorted(fert_rows, key=lambda r: -flt(r["qty_kg"]))[:TOP_FERTILIZERS]

	return {
		"totals": {
			"count": cint(agg.count),
			"this_month": cint(this_month.count),
			"plants": fmt(agg.plants, 0),
			"qty_kg": fmt(agg.qty_kg),
			"amount": inr0(agg.amount),
		},
		"tabs": tabs,
		"recent": recent,
		"fertilizers": [
			{
				"fertilizer_name": r["fertilizer_name"],
				"pack_kg": fmt(r["pack_kg"]),
				"qty_kg": fmt(r["qty_kg"]),
				"amount": inr0(r["amount"]),
			}
			for r in fert_rows
		],
	}


def _crop_names_of(names):
	out = defaultdict(list)
	if names:
		for c in frappe.get_all(
			"Basal Dose Crop",
			filters={"parent": ["in", names], "parenttype": BASAL},
			fields=["parent", "crop"],
			order_by="idx asc",
		):
			if c.crop not in out[c.parent]:
				out[c.parent].append(c.crop)
	return out


def _date(value, label):
	if not value:
		return None
	try:
		return getdate(value)
	except Exception:
		frappe.throw(_("{0} is not a valid date.").format(label))


@frappe.whitelist()
def get_crop_recommendations(
	crop, search=None, from_date=None, to_date=None, village=None, start=0, page_length=20
):
	"""One page of the recommendations that contain ``crop``, newest first."""
	_check_read()
	crop = cstr(crop)
	if not frappe.db.exists("Farm Crop", crop):
		frappe.throw(_("Unknown crop: {0}").format(crop))
	start = max(cint(start), 0)
	page_length = min(max(cint(page_length), 1), MAX_PAGE_LENGTH)

	filters = {"crops.crop": crop}
	from_date, to_date = _date(from_date, _("From Date")), _date(to_date, _("To Date"))
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["posting_date"] = [">=", from_date]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]
	if village:
		filters["village"] = cstr(village)
	or_filters = None
	search = cstr(search).strip()[:100]
	if search:
		like = f"%{search}%"
		or_filters = {
			"name": ["like", like],
			"farmer_name": ["like", like],
			"mobile_no": ["like", like],
			"customer": ["like", like],
		}

	matches = frappe.get_list(
		BASAL,
		filters=filters,
		or_filters=or_filters,
		fields=["name", "posting_date", "creation"],
		order_by="posting_date desc, creation desc",
		distinct=True,
	)
	page = [m.name for m in matches[start : start + page_length]]
	rows = []
	if page:
		parents = {
			p.name: p
			for p in frappe.get_list(
				BASAL,
				filters={"name": ["in", page]},
				fields=[
					"name",
					"posting_date",
					"farmer_name",
					"customer",
					"mobile_no",
					"village",
					"grand_total",
				],
			)
		}
		crop_rows = defaultdict(list)
		for c in frappe.get_all(
			"Basal Dose Crop",
			filters={"parent": ["in", page], "parenttype": BASAL, "crop": crop},
			fields=["parent", "variety", "area", "area_unit", "plant_count", "total_cost"],
			order_by="idx asc",
		):
			crop_rows[c.parent].append(c)
		varieties = _variety_names({c.variety for rs in crop_rows.values() for c in rs if c.variety})
		for name in page:
			p = parents.get(name)
			if not p:
				continue
			rs = crop_rows.get(name, [])
			rows.append(
				{
					"name": p.name,
					"date": frappe.format(p.posting_date, {"fieldtype": "Date"}),
					"farmer_name": p.farmer_name or "",
					"customer": p.customer or "",
					"mobile_no": p.mobile_no or "",
					"village": p.village or "",
					"variety": ", ".join(
						dict.fromkeys(varieties.get(c.variety, c.variety) for c in rs if c.variety)
					),
					"area": _area(rs),
					"plants": fmt(sum(cint(c.plant_count) for c in rs), 0),
					"crop_cost": inr0(sum(flt(c.total_cost) for c in rs)),
					"grand_total": inr0(p.grand_total),
				}
			)
	return {"total": len(matches), "start": start, "page_length": page_length, "rows": rows}


def _variety_names(names):
	if not names:
		return {}
	return {
		v.name: v.variety_name or v.name
		for v in frappe.get_all(
			"Farm Crop Variety", filters={"name": ["in", list(names)]}, fields=["name", "variety_name"]
		)
	}


def _area(rows):
	"""Area of the crop's rows, summed per unit ("2 Acre + 10 Guntha")."""
	by_unit = defaultdict(float)
	for c in rows:
		by_unit[c.area_unit or ""] += flt(c.area)
	return " + ".join(f"{fmt(v)} {unit}".strip() for unit, v in by_unit.items())
