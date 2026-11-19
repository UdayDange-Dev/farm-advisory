"""Unit conversions and plant counts shared by every calculator (utils/measure.py)."""

from frappe.tests import UnitTestCase

from farm_advisory.utils import basal_calc as B
from farm_advisory.utils import measure as M
from farm_advisory.utils import spray_calc as S


class TestConstants(UnitTestCase):
	def test_exact_definitions(self):
		# international foot (1959) and the US survey / Indian acre of 43 560 sq ft
		self.assertEqual(M.M_PER_FOOT, 0.3048)
		self.assertAlmostEqual(M.SQ_M_PER_ACRE, 4046.8564224, places=9)
		self.assertAlmostEqual(M.SQ_M_PER_GUNTHA, 101.17141056, places=9)
		self.assertAlmostEqual(M.SQ_M_PER_ACRE / M.SQ_M_PER_GUNTHA, 40, places=12)
		self.assertEqual(M.SQ_M_PER_HECTARE, 10000)
		self.assertAlmostEqual(M.convert_area(1, "Hectare", "Acre"), 2.4710538146716534, places=12)
		self.assertAlmostEqual(M.convert_area(1, "Acre", "Sq. Feet"), 43560, places=9)
		self.assertAlmostEqual(M.convert_area(1, "Guntha", "Sq. Feet"), 1089, places=9)

	def test_round_trip_has_no_drift(self):
		for unit in M.AREA_UNITS:
			for value in (0.25, 1, 7.5, 123.456):
				back = M.from_sq_m(M.to_sq_m(value, unit), unit)
				self.assertAlmostEqual(back, value, places=10, msg=unit)

	def test_lengths_and_rectangles(self):
		self.assertAlmostEqual(M.to_m(10, "Feet"), 3.048)
		self.assertEqual(M.to_m(10, "Metre"), 10)
		# a 66 × 660 ft strip is exactly one acre
		self.assertAlmostEqual(M.from_sq_m(M.rect_area_sq_m(66, 660, "Feet"), "Acre"), 1, places=12)
		self.assertEqual(M.rect_area_sq_m(0, 660, "Feet"), 0)


class TestPlantCount(UnitTestCase):
	def test_exact_fits_are_not_undercounted(self):
		# these used to lose one plant to truncated constants + floor
		self.assertEqual(M.plant_count(1, "Acre", 66, 66, "Feet"), 10)
		self.assertEqual(M.plant_count(1, "Guntha", 33, 33, "Feet"), 1)
		self.assertEqual(M.plant_count(1, "Acre", 22, 11, "Feet"), 180)
		self.assertEqual(M.plant_count(1, "Hectare", 5, 4, "Metre"), 500)

	def test_nearest_not_plus_one(self):
		# 193.6 → 194, 403.33 → 403: nearest, never a blanket +1
		self.assertEqual(M.plant_count(1, "Acre", 15, 15, "Feet"), 194)
		self.assertEqual(M.plant_count(1, "Acre", 12, 9, "Feet"), 403)
		self.assertEqual(M.plant_count(0.5, "Acre", 12, 9, "Feet"), 202)  # 201.67

	def test_missing_or_bad_input(self):
		self.assertEqual(M.plant_count(0, "Acre", 10, 10, "Feet"), 0)
		self.assertEqual(M.plant_count(1, "Acre", 0, 10, "Feet"), 0)
		self.assertEqual(M.plant_count(1, "Acre", 10, -5, "Feet"), 0)
		self.assertEqual(M.plant_count(None, "Acre", 10, 10, "Feet"), 0)

	def test_both_calculators_agree(self):
		for args in (
			(1, "Acre", 15, 15, "Feet"),
			(10, "Guntha", 3, 1.5, "Metre"),
			(2, "Hectare", 6, 3, "Metre"),
		):
			self.assertEqual(B.auto_plants(*args), S.auto_plants(*args), args)

	def test_spray_area_fields(self):
		self.assertAlmostEqual(S.area_sq_ft(1, "Hectare"), 107639.10416709722, places=6)
		self.assertAlmostEqual(S.area_acre(40, "Guntha"), 1, places=12)


class TestBasalPlot(UnitTestCase):
	def _crop(self, **kw):
		import frappe

		return frappe._dict(
			{
				"area": 0,
				"area_unit": "Acre",
				"spacing_unit": "Feet",
				"area_from_dimensions": 0,
				"plot_length": 0,
				"plot_width": 0,
				**kw,
			}
		)

	def test_area_from_dimensions(self):
		c = self._crop(area_from_dimensions=1, plot_length=66, plot_width=660, area=5)
		B.plot_area(c)
		self.assertAlmostEqual(c.area, 1, places=12)  # the typed 5 is replaced by L × W
		self.assertAlmostEqual(c.area_sq_m, 4046.8564224, places=6)
		self.assertAlmostEqual(c.area_acre, 1, places=12)

	def test_area_typed_in_other_units(self):
		c = self._crop(area=20, area_unit="Guntha")
		B.plot_area(c)
		self.assertEqual(c.area, 20)
		self.assertAlmostEqual(c.area_acre, 0.5, places=12)

	def test_dimensions_ignored_when_unticked_or_incomplete(self):
		c = self._crop(area=2, plot_length=100, plot_width=100)
		B.plot_area(c)
		self.assertEqual(c.area, 2)
		c = self._crop(area=2, area_from_dimensions=1, plot_length=100)
		B.plot_area(c)
		self.assertEqual(c.area, 2)
