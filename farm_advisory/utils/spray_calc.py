"""Spray Schedule calculation engine.

A line-for-line port of the application script in
``Spray_Schedule_Calculator.html`` (functions ``areaSq``, ``autoPlants``,
``totalWater``, ``ageText``, ``packSuggest``, ``rowCalc`` and ``calc``).

This module is the single source of truth: the form asks the server for a
preview on every edit and ``SpraySchedule.validate`` runs the same code on
save, so what the user sees is what gets stored and printed.
"""

import math

from frappe.utils import getdate, today

from farm_advisory.utils.i18n import tr
from farm_advisory.utils.numbers import js_round, num

# ``AUNITS`` — square feet per unit
AREA_UNITS = {"Acre": 43560.0, "Guntha": 1089.0, "Hectare": 107639.1}
# ``SUNITS`` — factor that converts the entered spacing to feet
SPACING_UNITS = {"Feet": 1.0, "Metre": 3.28084}
# ``WBASIS`` — default value loaded when the basis is changed
WATER_BASIS_DEFAULTS = {
	"Litres per acre": 200,
	"Litres per plant": 1,
	"Total water (manual)": 0,
}
# ``DUNITS`` — stored Select value -> prototype key
DOSE_UNITS = {"ml / L": "ml", "gm / L": "gm", "ppm (mg/L)": "ppm"}
# ``PACKS`` — standard pack sizes in ml / gm. The algorithm works in 50-unit
# steps, so every size here must be a multiple of 50.
PACK_SIZES = (100, 250, 500, 1000, 5000)


def dose_key(dose_unit):
	return DOSE_UNITS.get(dose_unit or "", "ml")


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def area_sq_ft(area, area_unit):
	return num(area) * AREA_UNITS.get(area_unit or "Acre", AREA_UNITS["Acre"])


def area_acre(area, area_unit):
	return area_sq_ft(area, area_unit) / 43560.0


def auto_plants(area, area_unit, row_spacing, plant_spacing, spacing_unit):
	"""``autoPlants``: ``Math.round(areaSq / (row × plant))`` in feet."""
	f = SPACING_UNITS.get(spacing_unit or "Feet", 1.0)
	r = num(row_spacing) * f
	p = num(plant_spacing) * f
	if r > 0 and p > 0:
		return js_round(area_sq_ft(area, area_unit) / (r * p))
	return 0


def total_water(basis, value, area, area_unit, plants):
	"""``totalWater``."""
	v = num(value)
	if basis == "Litres per acre":
		return v * area_acre(area, area_unit)
	if basis == "Litres per plant":
		return v * num(plants)
	return v


def tanks(water, capacity):
	"""Decimal tanks and the count of full/part loads (``Math.ceil(w/cap-1e-9)``)."""
	w, cap = num(water), num(capacity)
	if not (w and cap):
		return 0.0, 0
	return w / cap, math.ceil(w / cap - 1e-9)


# --------------------------------------------------------------------------- #
# Age
# --------------------------------------------------------------------------- #
def _days_in_month_before(d):
	"""JS ``new Date(y, m, 0).getDate()`` — length of the month before ``d``."""
	first = d.replace(day=1)
	import datetime

	return (first - datetime.timedelta(days=1)).day


def age(from_date, to_date=None, lang="both"):
	"""``ageText``: returns ``(text, total_days)``; to_date defaults to today."""
	if not from_date:
		return "", 0
	a = getdate(from_date)
	b = getdate(to_date) if to_date else getdate(today())
	if b < a:
		return tr("Date is in the future", "तारीख भविष्यातील आहे", lang), 0
	y = b.year - a.year
	m = b.month - a.month
	d = b.day - a.day
	if d < 0:
		m -= 1
		d += _days_in_month_before(b)
	if m < 0:
		y -= 1
		m += 12
	days = (b - a).days
	parts = []
	if y:
		parts.append(f"{y} {tr('yr', 'वर्ष', lang)}")
	if m:
		parts.append(f"{m} {tr('mo', 'महिने', lang)}")
	parts.append(f"{d} {tr('days', 'दिवस', lang)}")
	return " ".join(parts) + f"  ({days} {tr('days', 'दिवस', lang)})", days


# --------------------------------------------------------------------------- #
# Packs
# --------------------------------------------------------------------------- #
def pack_suggest(need):
	"""``packSuggest``: the smallest reachable total >= need, with fewest packs.

	Works in 50 ml/gm steps. Returns ``{"list": [{"size", "n"}], "total"}`` or
	``None`` when nothing is needed. Tie-breaking follows the prototype: the
	dynamic programme scans sizes smallest-first and only replaces a solution
	with a strictly better one.
	"""
	if need <= 0:
		return None
	n = math.ceil(need / 50 - 1e-9)
	sz = [p // 50 for p in PACK_SIZES]
	lim = n + 100
	inf = 10**9
	dp = [inf] * (lim + 1)
	pr = [None] * (lim + 1)
	dp[0] = 0
	for i in range(1, lim + 1):
		for j, s in enumerate(sz):
			if s <= i and dp[i - s] + 1 < dp[i]:
				dp[i] = dp[i - s] + 1
				pr[i] = j
	target = n
	while target <= lim and dp[target] >= inf:
		target += 1
	if target > lim:
		return None
	count = {}
	x = target
	while x > 0:
		size = PACK_SIZES[pr[x]]
		count[size] = count.get(size, 0) + 1
		x -= sz[pr[x]]
	packs = [{"size": s, "n": count[s]} for s in sorted(count, reverse=True)]
	return {"list": packs, "total": target * 50}


def pack_label(size, base):
	big = "L" if base == "ml" else "kg"
	if size >= 1000:
		v = size / 1000
		return f"{int(v) if v == int(v) else v} {big}"
	return f"{size} {base}"


def pack_text(ps, base):
	if not ps:
		return "–"
	return " + ".join(f"{p['n']} × {pack_label(p['size'], base)}" for p in ps["list"])


# --------------------------------------------------------------------------- #
# Product row
# --------------------------------------------------------------------------- #
def row_calc(dose, dose_unit, rate, water, capacity):
	"""``rowCalc``. Quantities are in ml (for ml/L) or gm (gm/L and ppm).

	ppm is mg per litre, so ``dose × water / 1000`` is grams.
	"""
	key = dose_key(dose_unit)
	d = num(dose)
	base = "ml" if key == "ml" else "gm"
	big = "L" if base == "ml" else "kg"
	w, cap = num(water), num(capacity)
	total = d * w / 1000 if key == "ppm" else d * w
	tank = d * cap / 1000 if key == "ppm" else d * cap
	ps = pack_suggest(total)
	r = num(rate)
	return {
		"dose": d,
		"base": base,
		"big": big,
		"total": total,
		"qty_big": total / 1000,
		"tank": tank,
		"ps": ps,
		"pack_text": pack_text(ps, base),
		"amount": total / 1000 * r,
		"pack_amount": ps["total"] / 1000 * r if ps else 0.0,
	}


# --------------------------------------------------------------------------- #
# Whole document
# --------------------------------------------------------------------------- #
def apply_spray_calculation(doc):
	"""Recompute every derived field on a Spray Schedule (saved or not)."""
	lang = doc.get_lang() if hasattr(doc, "get_lang") else "both"

	doc.area_sq_ft = area_sq_ft(doc.area, doc.area_unit)
	doc.area_acre = doc.area_sq_ft / 43560.0
	if not doc.plants_manual:
		doc.plant_count = auto_plants(
			doc.area, doc.area_unit, doc.row_spacing, doc.plant_spacing, doc.spacing_unit
		)

	water = total_water(doc.water_basis, doc.water_value, doc.area, doc.area_unit, doc.plant_count)
	doc.total_water = water
	doc.tanks_required, doc.tank_loads = tanks(water, doc.tank_capacity)

	sprays = sorted(doc.get("sprays") or [], key=lambda s: s.idx or 0)
	first_spray_date = sprays[0].spray_date if sprays else None
	doc.crop_age, doc.crop_age_days = age(doc.plantation_date, first_spray_date, lang)
	doc.bahar_age, doc.bahar_age_days = age(doc.bahar_date, first_spray_date, lang)

	totals = {s.spray_no: [0.0, 0.0] for s in sprays}
	for row in doc.get("products") or []:
		c = row_calc(row.dose, row.dose_unit, row.rate, water, doc.tank_capacity)
		row.base_unit = c["base"]
		row.big_unit = c["big"]
		row.total_qty = c["total"]
		row.total_qty_big = c["qty_big"]
		row.per_tank_qty = c["tank"]
		row.pack_suggestion = c["pack_text"]
		row.pack_total_qty = c["ps"]["total"] if c["ps"] else 0
		row.amount = c["amount"]
		row.pack_amount = c["pack_amount"]
		if row.spray_no in totals:
			totals[row.spray_no][0] += c["amount"]
			totals[row.spray_no][1] += c["pack_amount"]

	grand = grand_pack = 0.0
	for s in sprays:
		s.spray_total, s.spray_pack_total = totals.get(s.spray_no, [0.0, 0.0])
		grand += s.spray_total
		grand_pack += s.spray_pack_total
	doc.grand_total = grand
	doc.grand_pack_total = grand_pack
	return doc
