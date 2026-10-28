"""Report contexts shared by the print formats and the in-form previews.

``fa_spray_context`` mirrors ``reportHTML()`` in the Spray prototype field by
field; ``fa_basal_context`` mirrors the Basal prototype's printable layout.
Both are exposed to Jinja (see ``hooks.jinja``).
"""

import frappe
from frappe.utils import cint, flt, formatdate, getdate, today

from farm_advisory.utils import i18n
from farm_advisory.utils.i18n import tr
from farm_advisory.utils.numbers import fmt, inr, inr0
from farm_advisory.utils.spray_calc import dose_key

BUNDLED_LOGO = "/assets/farm_advisory/images/agrismart_logo.png"
SPRAY_TEMPLATE = "farm_advisory/templates/print/spray_schedule.html"
BASAL_TEMPLATE = "farm_advisory/templates/print/basal_dose.html"


def dmy(value):
	"""``dmy()``: yyyy-mm-dd -> dd-mm-yyyy."""
	if not value:
		return ""
	d = getdate(value)
	return f"{d.day:02d}-{d.month:02d}-{d.year}"


def _settings():
	return frappe.get_cached_doc("Farm Advisory Settings")


def _mr(doctype, name, field):
	return frappe.db.get_value(doctype, name, field) if name else None


def _kv(label, value, cls=""):
	return {"label": label, "value": "" if value in (None, "") else str(value), "cls": cls}


# --------------------------------------------------------------------------- #
# Spray Schedule
# --------------------------------------------------------------------------- #
def fa_spray_context(doc):
	lang = doc.get_lang()

	def t(en, mr=None):
		return tr(en, mr, lang)

	s = _settings()
	branch = None
	branch_name = doc.branch or s.default_branch
	if branch_name and frappe.db.exists("Branch", branch_name):
		b = frappe.db.get_value(
			"Branch", branch_name, ["branch", "fa_branch_name_mr", "fa_address", "fa_phone"], as_dict=True
		)
		branch = {
			"label": t(b.branch, b.fa_branch_name_mr),
			"address": ", ".join(x.strip() for x in (b.fa_address or "").splitlines() if x.strip()),
			"phone": b.fa_phone or "",
		}

	whatsapp = doc.mobile_no if doc.whatsapp_same_as_mobile else doc.whatsapp_no
	farmer = [
		_kv(t("Name", "नाव"), doc.farmer_name, "w2"),
		_kv(t("Mobile", "मोबाईल"), doc.mobile_no),
		_kv(t("Address", "पत्ता"), doc.address_line(lang), "w2"),
		_kv(t("WhatsApp", "व्हॉट्सअ‍ॅप"), whatsapp),
	]
	if doc.email_id:
		farmer.append(_kv(t("Email", "ई-मेल"), doc.email_id, "w3"))

	crop_label = t(doc.crop, _mr("Farm Crop", doc.crop, "crop_name_mr")) if doc.crop else ""
	variety_label = ""
	if doc.variety:
		v = (
			frappe.db.get_value(
				"Farm Crop Variety", doc.variety, ["variety_name", "variety_name_mr"], as_dict=True
			)
			or {}
		)
		variety_label = t(v.get("variety_name") or doc.variety, v.get("variety_name_mr"))
	equipment = ""
	if doc.spray_equipment:
		equipment = t(doc.spray_equipment, _mr("Spray Equipment", doc.spray_equipment, "equipment_name_mr"))
		if flt(doc.tank_capacity):
			equipment += f" – {fmt(doc.tank_capacity, 0)} L"
	water = flt(doc.total_water)
	cap = flt(doc.tank_capacity)
	plants = flt(doc.plant_count)
	crop = [
		_kv(t("Crop", "पीक"), crop_label),
		_kv(t("Variety", "वाण"), variety_label),
		_kv(t("Plantation date", "लागवड तारीख"), dmy(doc.plantation_date)),
		_kv(t("Crop age", "पिकाचे वय"), doc.crop_age, "w2"),
		_kv(
			t("Bahar / pruning", "बहार / छाटणी"),
			"" if doc.bahar in (None, "", "Not applicable") else i18n.opt(doc.bahar, i18n.BAHAR, lang),
		),
		_kv(t("Bahar date", "बहार तारीख"), dmy(doc.bahar_date)),
		_kv(t("Days since bahar", "बहारानंतर दिवस"), doc.bahar_age, "w2"),
		_kv(
			t("Area", "क्षेत्र"),
			f"{fmt(doc.area, 4)} {i18n.opt(doc.area_unit, i18n.AREA_UNITS, lang)}" if flt(doc.area) else "",
		),
		_kv(
			t("Spacing (row × plant)", "अंतर (ओळ × झाड)"),
			f"{fmt(doc.row_spacing, 4)} × {fmt(doc.plant_spacing, 4)} "
			f"{i18n.opt(doc.spacing_unit, i18n.SPACING_UNITS, lang)}"
			if flt(doc.row_spacing) and flt(doc.plant_spacing)
			else "",
		),
		_kv(t("No. of plants", "झाडांची संख्या"), fmt(plants, 0) if plants else ""),
		_kv(
			t("Total water", "एकूण पाणी"),
			f"{fmt(water, 1)} L ({fmt(doc.water_value, 4)} "
			f"{i18n.opt(doc.water_basis, i18n.WATER_BASIS, lang)})"
			if water
			else "",
			"w2",
		),
		_kv(t("Spray unit", "फवारणी यंत्र"), equipment),
		_kv(t("Tanks needed", "टाक्या"), str(cint(doc.tank_loads)) if water and cap else ""),
	]

	sprays = []
	products = doc.get("products") or []
	for sp in sorted(doc.get("sprays") or [], key=lambda x: x.spray_no or 0):
		rows = []
		for i, p in enumerate([p for p in products if p.spray_no == sp.spray_no], start=1):
			unit = dose_key(p.dose_unit)
			rows.append(
				{
					"no": i,
					"category": i18n.opt(p.category, i18n.SPRAY_CATEGORIES, lang),
					"product": t(p.product_name or p.product, p.product_name_mr),
					"dose": f"{fmt(p.dose, 2)} {unit}" if flt(p.dose) else "–",
					"total": f"{fmt(p.total_qty, 1)} {p.base_unit or ''}",
					"total_big": f"{fmt(p.total_qty_big, 3)} {p.big_unit or ''}",
					"tank": f"{fmt(p.per_tank_qty, 1)} {p.base_unit or ''}" if cap else "–",
					"packs": p.pack_suggestion or "–",
					"rate": fmt(p.rate, 2) if flt(p.rate) else "–",
					"amount": fmt(p.amount, 2),
				}
			)
		sprays.append(
			{
				"title": f"{t('Spray', 'फवारणी')} {sp.spray_no}",
				"date": dmy(sp.spray_date) or "__ / __ / ____",
				"rows": rows,
				"total": fmt(sp.spray_total, 2),
			}
		)

	L = {
		"title": t("SPRAY SCHEDULE", "फवारणी वेळापत्रक"),
		"phone": t("Phone", "फोन"),
		"farmer": t("Farmer details", "शेतकऱ्याची माहिती"),
		"crop": t("Crop & plot details", "पीक व प्लॉट माहिती"),
		"date": t("Date", "तारीख"),
		"category": t("Category", "प्रकार"),
		"product": t("Product", "उत्पादन"),
		"dose": t("Dose /L water", "मात्रा/लि. पाणी"),
		"total": t("Total qty", "एकूण प्रमाण"),
		"tank": t("Per tank", "प्रति टाकी"),
		"packs": t("Packs", "पॅक"),
		"rate": t("Rate ₹/L-kg", "दर ₹/लि-किलो"),
		"amount": t("Amount ₹", "रक्कम ₹"),
		"spray_total": t("Spray total", "फवारणी एकूण"),
		"grand": t("GRAND TOTAL", "एकूण रक्कम"),
		"pack_value": t(
			"Value at full pack sizes (100 / 250 / 500 ml-gm, 1 / 5 L-kg)",
			"पूर्ण पॅकनुसार किंमत (100 / 250 / 500 मिली-ग्रॅ, 1 / 5 लि-किलो)",
		),
		"disclaimer": t(
			"Doses are as entered by the advisor. Always follow the label recommendation "
			"and safety precautions. Quantities are calculated as Dose × Water required.",
			"मात्रा सल्लागाराने भरल्यानुसार आहे. नेहमी लेबलवरील शिफारस व सुरक्षा सूचना पाळा. "
			"प्रमाण = मात्रा × लागणारे पाणी.",
		),
		"sign_farmer": t("Farmer signature", "शेतकरी सही"),
		"sign_company": t("Agri Smart – Authorised signatory", "ॲग्री स्मार्ट – अधिकृत सही"),
		"generated": t("Generated on", "तयार केल्याची तारीख"),
	}
	return frappe._dict(
		lang=lang,
		L=L,
		logo=s.report_logo or BUNDLED_LOGO,
		company=s.company_name,
		email=s.report_email,
		tagline=s.report_tagline,
		branch=branch,
		farmer=farmer,
		crop=crop,
		sprays=sprays,
		grand=inr(doc.grand_total),
		grand_pack=inr(doc.grand_pack_total),
		generated_on=dmy(today()),
		doc_name=doc.name if not doc.is_new() else "",
	)


# --------------------------------------------------------------------------- #
# Basal Dose
# --------------------------------------------------------------------------- #
def fa_basal_context(doc):
	s = _settings()
	crops = []
	ferts = doc.get("fertilizers") or []
	for c in sorted(doc.get("crops") or [], key=lambda x: x.crop_no or 0):
		variety = frappe.db.get_value("Farm Crop Variety", c.variety, "variety_name") if c.variety else ""
		rows = []
		for i, r in enumerate([r for r in ferts if r.crop_no == c.crop_no], start=1):
			rows.append(
				{
					"no": i,
					"fertilizer": r.fertilizer_name or r.fertilizer or "",
					"pack": fmt(r.pack_kg),
					"contains": r.contains or "",
					"rate": fmt(r.rate, 4),
					"unit": r.rate_unit or "",
					"kg": fmt(r.qty_kg),
					"bags": fmt(r.bags, 2),
					"cost": fmt(r.cost_per_bag, 2),
					"perkg": fmt(r.cost_per_kg),
					"amount": inr0(r.amount),
					"cpp": fmt(r.cost_per_plant),
				}
			)
		crops.append(
			{
				"title": c.crop + (f" – {variety}" if variety else ""),
				"crop": c.crop,
				"variety": variety or "—",
				"details": [
					("Row spacing", f"{fmt(c.row_spacing, 4)} {c.spacing_unit}"),
					("Plant spacing", f"{fmt(c.plant_spacing, 4)} {c.spacing_unit}"),
					("Area", f"{fmt(c.area)} {c.area_unit}"),
					("No. of plants", fmt(c.plant_count, 0) + (" (manual)" if c.plants_manual else "")),
				],
				"rows": rows,
				"t_gm": fmt(c.dose_gm_per_plant),
				"t_kg": fmt(c.total_qty_kg),
				"t_bags": fmt(c.total_bags, 2),
				"t_amount": inr0(c.total_cost),
				"t_cpp": "₹ " + fmt(c.cost_per_plant),
				"plants": fmt(c.plant_count, 0),
				"area": f"{fmt(c.area)} {c.area_unit}",
			}
		)
	purchase = [
		{"name": p.fertilizer_name, "pack": fmt(p.pack_kg), "kg": fmt(p.qty_kg), "amount": inr0(p.amount)}
		for p in doc.get("purchase_items") or []
	]
	return frappe._dict(
		company=s.company_name,
		logo=s.report_logo or BUNDLED_LOGO,
		farmer_name=doc.farmer_name or "Farmer",
		address=doc.address_line("en"),
		mobile=doc.mobile_no or "",
		whatsapp=doc.whatsapp_no or "",
		email=doc.email_id or "",
		printed_on=formatdate(today(), "dd-mm-yyyy"),
		rounding=doc.bag_rounding,
		crops=crops,
		purchase=purchase,
		# the prototype prints it from two lines; a multi-crop record always shows it
		show_purchase=len(purchase) > 1 or (len(crops) > 1 and bool(purchase)),
		crop_count=len(crops),
		total_plants=fmt(doc.total_plants, 0),
		total_kg=fmt(doc.total_qty_kg),
		grand=inr0(doc.grand_total),
		doc_name=doc.name if not doc.is_new() else "",
	)


def render_spray_html(doc):
	return frappe.render_template(SPRAY_TEMPLATE, {"r": fa_spray_context(doc)})


def render_basal_html(doc):
	return frappe.render_template(BASAL_TEMPLATE, {"r": fa_basal_context(doc)})
