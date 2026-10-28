"""WhatsApp text, CSV export and legacy-file import.

``spray_whatsapp_text`` = ``waText()``, ``basal_whatsapp_text`` = ``shareWA()``
and ``basal_csv`` = ``exportCSV()`` from the reference calculators.
"""

import csv
import io
import json

import frappe
from frappe import _

from farm_advisory.utils.i18n import tr
from farm_advisory.utils.numbers import fmt, inr, inr0, js_round, num
from farm_advisory.utils.report import dmy
from farm_advisory.utils.spray_calc import dose_key

BASAL_AREA_KEYS = {"Acre": "acre", "Hectare": "ha", "Guntha": "guntha"}


def js_str(x):
	"""JavaScript ``String(number)`` for the values the prototypes printed raw."""
	x = num(x)
	return str(int(x)) if float(x).is_integer() else repr(x)


def _unit_short(rate_unit):
	return (rate_unit or "gm / plant").split(" ")[0]


# --------------------------------------------------------------------------- #
def spray_whatsapp_text(doc):
	lang = doc.get_lang()

	def t(en, mr=None):
		return tr(en, mr, lang)

	s = frappe.get_cached_doc("Farm Advisory Settings")
	lines = [f"*{s.company_name}*"]
	branch = doc.branch or s.default_branch
	if branch and frappe.db.exists("Branch", branch):
		b = frappe.db.get_value("Branch", branch, ["fa_branch_name_mr", "fa_phone"], as_dict=True)
		lines.append(f"{t(branch, b.fa_branch_name_mr)} | {b.fa_phone or ''}")
	lines.append(f"*{t('Spray Schedule', 'फवारणी वेळापत्रक')}*")
	lines.append(f"{t('Farmer', 'शेतकरी')}: {doc.farmer_name or ''}")
	crop = t(doc.crop, frappe.db.get_value("Farm Crop", doc.crop, "crop_name_mr")) if doc.crop else ""
	variety = frappe.db.get_value("Farm Crop Variety", doc.variety, "variety_name") if doc.variety else ""
	lines.append(f"{t('Crop', 'पीक')}: {crop} ({variety or ''})")
	if doc.crop_age:
		lines.append(f"{t('Age', 'वय')}: {doc.crop_age}")
	lines.append(
		f"{t('Area', 'क्षेत्र')}: {js_str(doc.area) if num(doc.area) else ''} {(doc.area_unit or '').lower()}"
		f" | {t('Plants', 'झाडे')}: {doc.plant_count or '–'}"
	)
	lines.append(f"{t('Water', 'पाणी')}: {fmt(doc.total_water, 1)} L")
	grand = 0.0
	products = doc.get("products") or []
	for sp in sorted(doc.get("sprays") or [], key=lambda x: x.spray_no or 0):
		lines.append("")
		lines.append(
			f"*{t('Spray', 'फवारणी')} {sp.spray_no}*" + (f" – {dmy(sp.spray_date)}" if sp.spray_date else "")
		)
		for i, p in enumerate([p for p in products if p.spray_no == sp.spray_no], start=1):
			grand += num(p.amount)
			line = (
				f"{i}. {t(p.product_name or p.product, p.product_name_mr)} – {fmt(p.dose, 2)} "
				f"{dose_key(p.dose_unit)} → {fmt(p.total_qty, 1)} {p.base_unit} [{p.pack_suggestion}]"
			)
			if num(p.rate):
				line += f" = {inr(p.amount)}"
			lines.append(line)
	lines.append("")
	lines.append(f"*{t('Total', 'एकूण')}: {inr(grand)}*")
	return "\n".join(lines)


def basal_whatsapp_text(doc):
	text = f"*Basal Fertilizer Dose*\nFarmer: {doc.farmer_name or 'Farmer'}\n"
	grand = 0.0
	ferts = doc.get("fertilizers") or []
	for c in sorted(doc.get("crops") or [], key=lambda x: x.crop_no or 0):
		grand += num(c.total_cost)
		variety = frappe.db.get_value("Farm Crop Variety", c.variety, "variety_name") if c.variety else ""
		text += f"\n*{c.crop}{' – ' + variety if variety else ''}* ({fmt(c.plant_count, 0)} plants)\n"
		for r in ferts:
			if r.crop_no == c.crop_no and (r.fertilizer_name or r.fertilizer):
				text += (
					f"• {r.fertilizer_name or r.fertilizer}: {js_str(r.rate)} {_unit_short(r.rate_unit)}/plant"
					f" → {fmt(r.qty_kg)} kg ({fmt(r.bags, 2)} bags)\n"
				)
		text += (
			f"Dose/plant: {fmt(c.dose_gm_per_plant)} gm | Cost/plant: ₹{fmt(c.cost_per_plant)} | "
			f"Total: {inr0(c.total_cost)}\n"
		)
	text += f"\n*Grand Total: {inr0(grand)}*"
	return text


# --------------------------------------------------------------------------- #
def basal_csv(doc):
	buf = io.StringIO()
	w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
	w.writerow(["Farmer", doc.farmer_name or "Farmer"])
	w.writerow(
		[
			"Address",
			", ".join(x for x in (doc.village, doc.taluka, doc.district, doc.state, doc.pin_code) if x),
		]
	)
	w.writerow(
		["Mobile", doc.mobile_no or "", "WhatsApp", doc.whatsapp_no or "", "Email", doc.email_id or ""]
	)
	ferts = doc.get("fertilizers") or []
	for c in sorted(doc.get("crops") or [], key=lambda x: x.crop_no or 0):
		variety = frappe.db.get_value("Farm Crop Variety", c.variety, "variety_name") if c.variety else ""
		buf.write("\r\n")
		w.writerow(
			[
				c.crop,
				variety or "",
				"Plants",
				c.plant_count,
				"Area",
				f"{js_str(c.area)} {BASAL_AREA_KEYS.get(c.area_unit, c.area_unit)}",
			]
		)
		w.writerow(
			[
				"Sr",
				"Fertilizer",
				"Pack kg",
				"Contains",
				"Rate",
				"Unit",
				"Total qty kg",
				"Bags",
				"Cost/bag",
				"Total Rs",
				"Rs/plant",
			]
		)
		rows = [r for r in ferts if r.crop_no == c.crop_no]
		for i, r in enumerate(rows, start=1):
			w.writerow(
				[
					i,
					r.fertilizer_name or r.fertilizer or "",
					js_str(r.pack_kg),
					r.contains or "",
					js_str(r.rate),
					_unit_short(r.rate_unit) + "/plant",
					f"{num(r.qty_kg):.2f}",
					js_str(r.bags),
					js_str(r.cost_per_bag),
					js_round(r.amount),
					f"{num(r.cost_per_plant):.2f}",
				]
			)
		w.writerow(
			[
				"",
				"TOTAL",
				"",
				"",
				f"{num(c.dose_gm_per_plant):.0f} gm/plant",
				"",
				f"{num(c.total_qty_kg):.2f}",
				js_str(c.total_bags),
				"",
				js_round(c.total_cost),
				f"{num(c.cost_per_plant):.2f}",
			]
		)
	# a BOM so Excel opens the file as UTF-8 (Marathi names stay readable)
	return "﻿" + buf.getvalue().rstrip("\r\n")


# --------------------------------------------------------------------------- #
LEGACY_SPACING = {"ft": "Feet", "m": "Metre"}
LEGACY_AREA = {"acre": "Acre", "ha": "Hectare", "guntha": "Guntha"}
LEGACY_UNIT = {"gm": "gm / plant", "kg": "kg / plant"}
LEGACY_ROUNDING = {
	"up": "Round up (full bags)",
	"near": "Nearest bag (like Excel)",
	"none": "No rounding (exact)",
}


def _ensure_location(doctype, key, value):
	value = (value or "").strip()
	if not value:
		return None
	if frappe.db.exists(doctype, value):
		return value
	if not frappe.has_permission(doctype, "create"):
		return None
	frappe.get_doc({"doctype": doctype, f"{key}_name": value}).insert()
	return value


def parse_legacy_basal(content):
	"""Turn a file saved by the HTML Basal calculator ("💾 Save") into field values.

	Locations missing from the masters are created (the old tool's "＋" lists);
	fertilizers missing from the master are kept by name on the row.
	"""
	try:
		data = json.loads(content)
	except ValueError:
		frappe.throw(_("This is not a valid calculator file."))
	if not isinstance(data, dict) or "crops" not in data:
		frappe.throw(_("This file does not look like a Basal Dose calculator file."))
	f = data.get("farmer") or {}
	out = {
		"first_name": f.get("fn"),
		"middle_name": f.get("mn"),
		"last_name": f.get("ln"),
		"village": _ensure_location("Farm Village", "village", f.get("village")),
		"taluka": _ensure_location("Farm Taluka", "taluka", f.get("taluka")),
		"district": _ensure_location("Farm District", "district", f.get("district")),
		"state": _ensure_location("Farm State", "state", f.get("state")),
		"pin_code": f.get("pin"),
		"mobile_no": f.get("mobile"),
		"whatsapp_no": f.get("wa"),
		"whatsapp_same_as_mobile": 1 if (f.get("wa") or "") == (f.get("mobile") or "") else 0,
		"email_id": f.get("email"),
		"bag_rounding": LEGACY_ROUNDING.get(data.get("rnd"), "Round up (full bags)"),
		"crops": [],
		"fertilizers": [],
	}
	for i, c in enumerate(data.get("crops") or [], start=1):
		crop = c.get("crop")
		if not frappe.db.exists("Farm Crop", crop):
			frappe.throw(_("Crop {0} is not set up in Farm Crop.").format(crop))
		variety = f"{crop} - {c.get('variety')}" if c.get("variety") else None
		out["crops"].append(
			{
				"crop_no": i,
				"crop": crop,
				"variety": variety if variety and frappe.db.exists("Farm Crop Variety", variety) else None,
				"row_spacing": num(c.get("rs")),
				"plant_spacing": num(c.get("ps")),
				"spacing_unit": LEGACY_SPACING.get(c.get("su"), "Feet"),
				"area": num(c.get("area")),
				"area_unit": LEGACY_AREA.get(c.get("au"), "Acre"),
				"plant_count": int(num(c.get("plants"))),
				"plants_manual": 1 if c.get("manual") else 0,
			}
		)
		for r in c.get("rows") or []:
			name = (r.get("f") or "").strip()
			if not name and not num(r.get("rate")):
				continue
			out["fertilizers"].append(
				{
					"crop_no": i,
					"fertilizer": name if frappe.db.exists("Farm Fertilizer", name) else None,
					"fertilizer_name": name,
					"pack_kg": num(r.get("pack")),
					"contains": r.get("contain"),
					"rate": num(r.get("rate")),
					"rate_unit": LEGACY_UNIT.get(r.get("unit"), "gm / plant"),
					"cost_per_bag": num(r.get("cost")),
				}
			)
	return out
