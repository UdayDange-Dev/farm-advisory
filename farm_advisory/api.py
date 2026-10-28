"""Whitelisted endpoints used by the Spray Schedule and Basal Dose forms.

The previews run the *same* calculation as ``validate()`` on an unsaved copy
of the form, so the browser never computes a figure the server would not.
"""

import frappe
from frappe import _
from frappe.utils import flt

from farm_advisory.utils.basal_calc import apply_basal_calculation
from farm_advisory.utils.report import render_basal_html, render_spray_html
from farm_advisory.utils.share import basal_csv, basal_whatsapp_text, parse_legacy_basal, spray_whatsapp_text
from farm_advisory.utils.spray_calc import apply_spray_calculation

SPRAY_PARENT = (
	"area_sq_ft",
	"area_acre",
	"plant_count",
	"total_water",
	"tanks_required",
	"tank_loads",
	"crop_age",
	"crop_age_days",
	"bahar_age",
	"bahar_age_days",
	"grand_total",
	"grand_pack_total",
)
SPRAY_SPRAY = ("spray_no", "spray_total", "spray_pack_total")
SPRAY_PRODUCT = (
	"spray_no",
	"base_unit",
	"big_unit",
	"total_qty",
	"total_qty_big",
	"per_tank_qty",
	"pack_suggestion",
	"pack_total_qty",
	"amount",
	"pack_amount",
)
BASAL_PARENT = ("total_plants", "total_qty_kg", "grand_total")
BASAL_CROP = (
	"crop_no",
	"plant_count",
	"dose_gm_per_plant",
	"total_qty_kg",
	"total_bags",
	"total_cost",
	"cost_per_plant",
)
BASAL_FERT = ("crop_no", "rate_gm", "qty_kg", "bags", "cost_per_kg", "amount", "cost_per_plant")


def _form_doc(doctype, doc):
	"""An unsaved Document built from the form, after a permission check."""
	data = frappe.parse_json(doc) if isinstance(doc, str) else doc
	if not isinstance(data, dict) or data.get("doctype") != doctype:
		frappe.throw(_("Invalid document"))
	name = data.get("name")
	if name and not data.get("__islocal") and frappe.db.exists(doctype, name):
		frappe.has_permission(doctype, "read", name, throw=True)
	else:
		frappe.has_permission(doctype, "create", throw=True)
	d = frappe.get_doc(data)
	d.farmer_name = " ".join(p for p in (d.first_name, d.middle_name, d.last_name) if p)
	if d.whatsapp_same_as_mobile:
		d.whatsapp_no = d.mobile_no
	return d


def _pick(obj, fields):
	return {f: obj.get(f) for f in fields}


def _rows(rows, fields):
	return {r.name: _pick(r, fields) for r in rows or [] if r.name}


@frappe.whitelist()
def preview_spray_schedule(doc):
	d = _form_doc("Spray Schedule", doc)
	d.normalise_sprays(strict=False)
	for p in d.products or []:
		if p.product and not p.product_name:
			p.product_name, p.product_name_mr = frappe.db.get_value(
				"Spray Product", p.product, ["product_name", "product_name_mr"]
			) or (p.product, None)
	apply_spray_calculation(d)
	return {
		"parent": _pick(d, SPRAY_PARENT),
		"sprays": _rows(d.sprays, SPRAY_SPRAY),
		"products": _rows(d.products, SPRAY_PRODUCT),
		"html": render_spray_html(d),
	}


@frappe.whitelist()
def preview_basal_dose(doc):
	d = _form_doc("Basal Dose Recommendation", doc)
	d.normalise_crops(strict=False)
	for f in d.fertilizers or []:
		if f.fertilizer and not f.fertilizer_name:
			f.fertilizer_name = frappe.db.get_value("Farm Fertilizer", f.fertilizer, "fertilizer_name")
	apply_basal_calculation(d)
	return {
		"parent": _pick(d, BASAL_PARENT),
		"crops": _rows(d.crops, BASAL_CROP),
		"fertilizers": _rows(d.fertilizers, BASAL_FERT),
		"purchase_items": [
			_pick(p, ("fertilizer_name", "pack_kg", "qty_kg", "amount")) for p in d.purchase_items
		],
		"html": render_basal_html(d),
	}


@frappe.whitelist()
def get_crop_defaults(crop):
	"""Default spacing and the basal fertilizer template for a crop.

	Mirrors ``rowFromTpl`` in the reference: a template override wins, else
	the fertilizer master's pack, contents and price are used.
	"""
	frappe.has_permission("Farm Crop", "read", crop, throw=True)
	c = frappe.get_doc("Farm Crop", crop)
	rows = []
	for t in c.fertilizer_template or []:
		f = (
			frappe.db.get_value(
				"Farm Fertilizer",
				t.fertilizer,
				["fertilizer_name", "pack_kg", "contains", "cost_per_bag"],
				as_dict=True,
			)
			or {}
		)
		rows.append(
			{
				"fertilizer": t.fertilizer,
				"fertilizer_name": f.get("fertilizer_name") or t.fertilizer,
				"pack_kg": flt(t.pack_kg) or flt(f.get("pack_kg")),
				"contains": t.contains or f.get("contains"),
				"cost_per_bag": flt(t.cost_per_bag) or flt(f.get("cost_per_bag")),
				"rate": flt(t.rate),
				"rate_unit": t.rate_unit or "gm / plant",
			}
		)
	return {
		"row_spacing": flt(c.default_row_spacing),
		"plant_spacing": flt(c.default_plant_spacing),
		"template": rows,
	}


@frappe.whitelist()
def get_first_spray_product(category):
	"""The prototype pre-selects the first product of a category."""
	return frappe.db.get_value(
		"Spray Product",
		{"category": category, "is_active": 1},
		["name", "default_dose_unit"],
		order_by="creation asc, name asc",
		as_dict=True,
	)


@frappe.whitelist()
def get_whatsapp_message(doctype, name):
	if doctype not in ("Spray Schedule", "Basal Dose Recommendation"):
		frappe.throw(_("Not supported"))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	if not doc.farmer_name:
		frappe.throw(_("Enter the farmer's name before sharing."))
	text = spray_whatsapp_text(doc) if doctype == "Spray Schedule" else basal_whatsapp_text(doc)
	return {"number": doc.whatsapp_target(), "text": text}


@frappe.whitelist()
def download_basal_csv(name):
	doc = frappe.get_doc("Basal Dose Recommendation", name)
	doc.check_permission("export")
	safe = "".join(ch if ch.isalnum() else "_" for ch in (doc.farmer_name or "Farmer"))
	frappe.response["type"] = "download"
	frappe.response["filename"] = f"basal-dose-{safe}.csv"
	frappe.response["filecontent"] = basal_csv(doc).encode("utf-8")
	frappe.response["content_type"] = "text/csv; charset=utf-8"


@frappe.whitelist()
def import_legacy_basal_file(content):
	"""Field values for a new Basal Dose Recommendation from an old calculator file."""
	frappe.has_permission("Basal Dose Recommendation", "create", throw=True)
	if len(content or "") > 2_000_000:
		frappe.throw(_("File is too large."))
	return parse_legacy_basal(content)
