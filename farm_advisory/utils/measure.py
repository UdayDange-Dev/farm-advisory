"""Agricultural measurement: one set of units for every Farm Advisory module.

Spray Schedule, Basal Dose Recommendation and Crop Consultation all convert
areas, lengths and plant spacing through this module, so the same plot gives
the same area and plant count everywhere.

Constants are exact, derived from the international foot (1 ft = 0.3048 m
exactly, by definition since 1959):

* 1 acre    = 43 560 sq ft = 4046.8564224 m²
* 1 guntha  = 1/40 acre    = 1089 sq ft  = 101.17141056 m²
* 1 hectare = 10 000 m²    ≈ 107 639.104 sq ft

Everything is computed in square metres with full float precision; nothing is
rounded until a value is shown or a whole plant count is needed.
"""

from farm_advisory.utils.numbers import js_round, num

M_PER_FOOT = 0.3048
SQ_M_PER_SQ_FOOT = M_PER_FOOT * M_PER_FOOT  # 0.09290304
SQ_M_PER_ACRE = 43560 * SQ_M_PER_SQ_FOOT  # 4046.8564224
SQ_M_PER_GUNTHA = SQ_M_PER_ACRE / 40  # 101.17141056
SQ_M_PER_HECTARE = 10000.0

# square metres per area unit (the Select values stored on the documents)
AREA_UNITS = {
	"Acre": SQ_M_PER_ACRE,
	"Guntha": SQ_M_PER_GUNTHA,
	"Hectare": SQ_M_PER_HECTARE,
	"Sq. Metre": 1.0,
	"Sq. Feet": SQ_M_PER_SQ_FOOT,
}
# metres per length / spacing unit
LENGTH_UNITS = {"Feet": M_PER_FOOT, "Metre": 1.0}

DEFAULT_AREA_UNIT = "Acre"
DEFAULT_LENGTH_UNIT = "Feet"


def area_factor(unit):
	return AREA_UNITS.get(unit or DEFAULT_AREA_UNIT, AREA_UNITS[DEFAULT_AREA_UNIT])


def length_factor(unit):
	return LENGTH_UNITS.get(unit or DEFAULT_LENGTH_UNIT, LENGTH_UNITS[DEFAULT_LENGTH_UNIT])


def to_sq_m(area, unit):
	"""An area in ``unit`` as square metres."""
	return num(area) * area_factor(unit)


def from_sq_m(area_sq_m, unit):
	"""Square metres expressed in ``unit``."""
	return num(area_sq_m) / area_factor(unit)


def convert_area(area, from_unit, to_unit):
	"""Convert once, through square metres (never chain unit to unit)."""
	return from_sq_m(to_sq_m(area, from_unit), to_unit)


def to_m(length, unit):
	return num(length) * length_factor(unit)


def rect_area_sq_m(length, width, unit):
	"""Area of a rectangular plot measured as length × width in ``unit``."""
	return to_m(length, unit) * to_m(width, unit)


def area_per_plant_sq_m(row_spacing, plant_spacing, spacing_unit):
	return to_m(row_spacing, spacing_unit) * to_m(plant_spacing, spacing_unit)


def plants_estimate(area, area_unit, row_spacing, plant_spacing, spacing_unit):
	"""Unrounded plant density: plot area ÷ area one plant occupies (row × plant)."""
	per_plant = area_per_plant_sq_m(row_spacing, plant_spacing, spacing_unit)
	if per_plant <= 0:
		return 0.0
	return to_sq_m(area, area_unit) / per_plant


def plant_count(area, area_unit, row_spacing, plant_spacing, spacing_unit):
	"""Whole plants for a plot, from its area and spacing.

	``area ÷ (row spacing × plant spacing)`` is the standard planting-density
	formula. It knows the area but not the plot's shape, so it is an estimate
	of the plants on that area: it neither adds the extra row a planted border
	can carry nor removes the half-cells along the edges. The estimate is
	rounded to the *nearest* whole plant (halves up, like JavaScript
	``Math.round``): the result is never more than half a plant from the
	estimate, where rounding down was on average half a plant low and, with
	the old truncated constants, lost a whole plant on exact fits (1 acre at
	66 × 66 ft gave 9 instead of 10). When the actual count is known, the forms
	take it as a manual entry instead.
	"""
	x = plants_estimate(area, area_unit, row_spacing, plant_spacing, spacing_unit)
	return js_round(x) if x > 0 else 0
