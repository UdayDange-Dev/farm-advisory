"""Unit tests for the two calculation engines.

Expected values are worked by hand from the formulas in the reference HTML
files (and were cross-checked against the original JavaScript, see README).
"""

from frappe.tests import UnitTestCase

from farm_advisory.utils import basal_calc as B
from farm_advisory.utils import spray_calc as S
from farm_advisory.utils.numbers import fmt, inr, js_round


class TestNumbers(UnitTestCase):
	def test_js_round_half_up(self):
		self.assertEqual(js_round(2.5), 3)
		self.assertEqual(js_round(0.5), 1)  # Python's round() is banker's: round(2.5) == 2
		self.assertEqual(js_round(-2.5), -2)

	def test_indian_grouping(self):
		self.assertEqual(fmt(1234567.891, 2), "12,34,567.89")
		self.assertEqual(fmt(1000, 1), "1,000")
		self.assertEqual(fmt(0.5, 0), "1")
		self.assertEqual(inr(1250), "₹ 1,250.00")


class TestSprayCalc(UnitTestCase):
	def test_area_and_plants(self):
		# 1 acre, 12 × 9 ft  → 43560 / 108 = 403.33 → 403
		self.assertEqual(S.auto_plants(1, "Acre", 12, 9, "Feet"), 403)
		# Guntha is 1089 sq ft; metres convert at 3.28084 ft
		self.assertEqual(S.auto_plants(1, "Guntha", 3, 3, "Metre"), js_round(1089 / (3 * 3.28084) ** 2))
		self.assertEqual(S.auto_plants(1, "Acre", 0, 9, "Feet"), 0)

	def test_water_bases(self):
		self.assertAlmostEqual(S.total_water("Litres per acre", 200, 2, "Acre", 0), 400)
		self.assertAlmostEqual(S.total_water("Litres per acre", 200, 1, "Hectare", 0), 200 * 107639.1 / 43560)
		self.assertEqual(S.total_water("Litres per plant", 1.5, 1, "Acre", 403), 604.5)
		self.assertEqual(S.total_water("Total water (manual)", 750, 9, "Acre", 9), 750)

	def test_tanks(self):
		self.assertEqual(S.tanks(400, 200), (2.0, 2))
		self.assertEqual(S.tanks(401, 200), (2.005, 3))
		self.assertEqual(S.tanks(0, 200), (0.0, 0))

	def test_pack_suggestion(self):
		self.assertIsNone(S.pack_suggest(0))
		# 120 ml → 3 units of 50 cannot be made from 100/250 → next reachable is 200 ml
		self.assertEqual(S.pack_suggest(120), {"list": [{"size": 100, "n": 2}], "total": 200})
		# 1200 ml → 1 L + 2 × 100 ml (fewest packs for 1200)
		self.assertEqual(S.pack_suggest(1200)["total"], 1200)
		self.assertEqual(S.pack_text(S.pack_suggest(5000), "ml"), "1 × 5 L")
		self.assertEqual(S.pack_text(S.pack_suggest(350), "gm"), "1 × 250 gm + 1 × 100 gm")

	def test_row_calc_units(self):
		ml = S.row_calc(2, "ml / L", 1500, 400, 200)
		self.assertEqual((ml["total"], ml["tank"], ml["base"], ml["big"]), (800, 400, "ml", "L"))
		self.assertAlmostEqual(ml["amount"], 0.8 * 1500)
		self.assertAlmostEqual(ml["pack_amount"], 0.8 * 1500)  # 800 ml = 500 + 3 × 100, exact
		gm = S.row_calc(2.5, "gm / L", 0, 400, 16)
		self.assertEqual((gm["total"], gm["tank"], gm["base"]), (1000, 40, "gm"))
		# ppm is mg/L: 500 ppm × 400 L = 200 000 mg = 200 gm
		ppm = S.row_calc(500, "ppm (mg/L)", 0, 400, 200)
		self.assertEqual((ppm["total"], ppm["tank"], ppm["base"]), (200, 100, "gm"))

	def test_age(self):
		self.assertEqual(S.age("2025-01-15", "2026-03-10", "en"), ("1 yr 1 mo 23 days  (419 days)", 419))
		self.assertEqual(S.age("2026-03-10", "2026-03-10", "en"), ("0 days  (0 days)", 0))
		self.assertEqual(S.age("2026-03-11", "2026-03-10", "en")[0], "Date is in the future")
		self.assertIn("वर्ष", S.age("2025-01-15", "2026-03-10", "mr")[0])


class TestBasalCalc(UnitTestCase):
	def test_plants_floor(self):
		# Mango 15 × 15 ft on 1 acre: 4046.856 / 4.572² = 193.6 → floor 193 (not 194)
		self.assertEqual(B.auto_plants(1, "Acre", 15, 15, "Feet"), 193)
		self.assertEqual(B.auto_plants(1, "Hectare", 5, 4, "Metre"), 500)
		self.assertEqual(B.auto_plants(10, "Guntha", 0, 4, "Metre"), 0)

	def test_bag_rounding(self):
		self.assertEqual(B.bags_of(9.65, 25, B.ROUND_UP), 1)
		self.assertEqual(B.bags_of(25.0, 25, B.ROUND_UP), 1)  # 1e-9 tolerance: exact fit is one bag
		self.assertEqual(B.bags_of(9.65, 25, B.ROUND_NEAREST), 0)
		self.assertEqual(B.bags_of(12.5, 25, B.ROUND_NEAREST), 1)  # half rounds up, like Excel
		self.assertAlmostEqual(B.bags_of(9.65, 25, B.ROUND_NONE), 0.386)
		self.assertEqual(B.bags_of(10, 0, B.ROUND_UP), 0)

	def test_row(self):
		r = B.row_calc(0.05, "kg / plant", 25, 1250, 193, B.ROUND_UP)
		self.assertEqual(r["gm"], 50)
		self.assertAlmostEqual(r["kg"], 9.65)
		self.assertEqual((r["bags"], r["amount"]), (1, 1250))
		self.assertEqual(r["cost_per_kg"], 50)
		self.assertAlmostEqual(r["cost_per_plant"], 1250 / 193)
		zero = B.row_calc(50, "gm / plant", 25, 1250, 0, B.ROUND_UP)
		self.assertEqual((zero["kg"], zero["cost_per_plant"]), (0, 0))
