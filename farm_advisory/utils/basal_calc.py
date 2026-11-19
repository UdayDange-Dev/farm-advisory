"""Fertilizer Basal Dose calculation engine.

A line-for-line port of ``basal-dose-calculator.html`` (``autoPlants``,
``bagsOf``, ``calcCrop`` and ``renderGrand``). Used by the live form preview
and by ``BasalDoseRecommendation.validate``.
"""

import math

from farm_advisory.utils import measure
from farm_advisory.utils.numbers import js_round, num
from farm_advisory.utils.spray_calc import age

# Area and spacing conversion lives in ``measure`` (exact constants, shared
# with Spray Schedule and Crop Consultation). Kept here as aliases for callers.
AREA_UNITS = measure.AREA_UNITS
SPACING_UNITS = measure.LENGTH_UNITS
RATE_UNITS = {"gm / plant": 1.0, "kg / plant": 1000.0}

ROUND_UP = "Round up (full bags)"
ROUND_NEAREST = "Nearest bag (like Excel)"
ROUND_NONE = "No rounding (exact)"


def auto_plants(area, area_unit, row_spacing, plant_spacing, spacing_unit):
	"""Plants from area and spacing — see ``measure.plant_count``.

	Previously ``Math.floor`` over truncated constants (acre 4046.856 m²,
	guntha 101.171 m²), which dropped a plant whenever the spacing fitted the
	area exactly. Now the shared nearest-whole-plant rule with exact constants.
	"""
	return measure.plant_count(area, area_unit, row_spacing, plant_spacing, spacing_unit)


def plot_area(crop):
	"""Apply a plot's length × width to its area when the row asks for it.

	The dimensions are in the row's spacing unit; the area keeps the row's
	area unit. Also fills the read-only m² / acre equivalents.
	"""
	if (
		crop.get("area_from_dimensions")
		and num(crop.get("plot_length")) > 0
		and num(crop.get("plot_width")) > 0
	):
		sq_m = measure.rect_area_sq_m(crop.plot_length, crop.plot_width, crop.spacing_unit)
		crop.area = measure.from_sq_m(sq_m, crop.area_unit)
	crop.area_sq_m = measure.to_sq_m(crop.area, crop.area_unit)
	crop.area_acre = measure.from_sq_m(crop.area_sq_m, "Acre")


def bags_of(qty_kg, pack_kg, rounding):
	pack = num(pack_kg)
	if not pack > 0:
		return 0.0
	x = qty_kg / pack
	if rounding == ROUND_NEAREST:
		return float(js_round(x))
	if rounding == ROUND_NONE:
		return x
	return float(math.ceil(x - 1e-9))


def row_calc(rate, rate_unit, pack_kg, cost_per_bag, plants, rounding):
	gm = num(rate) * RATE_UNITS.get(rate_unit or "gm / plant", 1.0)
	kg = gm * num(plants) / 1000
	bags = bags_of(kg, pack_kg, rounding)
	amt = bags * num(cost_per_bag)
	pack = num(pack_kg)
	return {
		"gm": gm,
		"kg": kg,
		"bags": bags,
		"amount": amt,
		"cost_per_kg": num(cost_per_bag) / pack if pack > 0 else 0.0,
		"cost_per_plant": amt / num(plants) if num(plants) > 0 else 0.0,
	}


def apply_basal_calculation(doc):
	"""Recompute every derived field on a Basal Dose Recommendation."""
	rounding = doc.bag_rounding or ROUND_UP
	crops = sorted(doc.get("crops") or [], key=lambda c: c.idx or 0)
	by_no = {}
	for c in crops:
		plot_area(c)
		c.crop_age = age(c.plantation_date, doc.posting_date, "en")[0] if c.get("plantation_date") else ""
		if not c.plants_manual:
			c.plant_count = auto_plants(c.area, c.area_unit, c.row_spacing, c.plant_spacing, c.spacing_unit)
		c.dose_gm_per_plant = c.total_qty_kg = c.total_bags = c.total_cost = 0.0
		by_no[c.crop_no] = c

	purchase = {}
	for r in doc.get("fertilizers") or []:
		c = by_no.get(r.crop_no)
		plants = c.plant_count if c else 0
		o = row_calc(r.rate, r.rate_unit, r.pack_kg, r.cost_per_bag, plants, rounding)
		r.rate_gm = o["gm"]
		r.qty_kg = o["kg"]
		r.bags = o["bags"]
		r.cost_per_kg = o["cost_per_kg"]
		r.amount = o["amount"]
		r.cost_per_plant = o["cost_per_plant"]
		if c:
			c.dose_gm_per_plant += o["gm"]
			c.total_qty_kg += o["kg"]
			c.total_bags += o["bags"]
			c.total_cost += o["amount"]
		if r.fertilizer_name:
			# the prototype keys on name + pack; never merge different packs
			key = (r.fertilizer_name, num(r.pack_kg))
			p = purchase.setdefault(key, {"qty_kg": 0.0, "amount": 0.0})
			p["qty_kg"] += o["kg"]
			p["amount"] += o["amount"]

	total_plants = total_kg = grand = 0.0
	for c in crops:
		c.cost_per_plant = c.total_cost / c.plant_count if num(c.plant_count) > 0 else 0.0
		total_plants += num(c.plant_count)
		total_kg += c.total_qty_kg
		grand += c.total_cost

	doc.total_plants = total_plants
	doc.total_qty_kg = total_kg
	doc.grand_total = grand
	doc.set("purchase_items", [])
	for (name, pack), v in purchase.items():
		doc.append(
			"purchase_items",
			{"fertilizer_name": name, "pack_kg": pack, "qty_kg": v["qty_kg"], "amount": v["amount"]},
		)
	return doc
