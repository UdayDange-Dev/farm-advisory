"""One Basal Dose Recommendation with several crops, each calculated on its own."""

import json
import re

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from farm_advisory import api
from farm_advisory.farm_advisory.page.basal_dose import basal_dose as page
from farm_advisory.farm_advisory.report.basal_dose_register import basal_dose_register
from farm_advisory.farm_advisory.report.fertilizer_requirement_summary import fertilizer_requirement_summary
from farm_advisory.tests.test_integration import MOBILE, _customer
from farm_advisory.utils.basal_calc import apply_basal_calculation
from farm_advisory.utils.farmer import create_customer
from farm_advisory.utils.numbers import fmt, inr0

BASAL = "Basal Dose Recommendation"
PRINT_FORMAT = "Basal Dose Recommendation Report"


def _crop(crop_no, crop, area=1, area_unit="Acre"):
	d = api.get_crop_defaults(crop)
	return {
		"crop_no": crop_no,
		"crop": crop,
		"row_spacing": d["row_spacing"],
		"plant_spacing": d["plant_spacing"],
		"spacing_unit": "Feet",
		"area": area,
		"area_unit": area_unit,
	}


def _template(crop_no, crop):
	return [{**t, "crop_no": crop_no} for t in api.get_crop_defaults(crop)["template"]]


def _three_crops(customer, **kw):
	"""Mango and Papaya with their templates; Banana (no template) with rows typed in by the user."""
	mango_first = api.get_crop_defaults("Mango")["template"][0]
	doc = frappe.get_doc(
		{
			"doctype": BASAL,
			"customer": customer,
			"first_name": "Ramesh",
			"last_name": "Patil",
			"mobile_no": MOBILE,
			"whatsapp_same_as_mobile": 1,
			"bag_rounding": "Round up (full bags)",
			"crops": [_crop(1, "Mango"), _crop(2, "Banana", 10, "Guntha"), _crop(3, "Papaya", 0.5)],
			"fertilizers": [
				*_template(1, "Mango"),
				# the same fertilizer and pack as Mango's first row, so the purchase list combines them
				{**mango_first, "crop_no": 2, "rate": 30},
				*_template(3, "Papaya"),
			],
		}
	)
	doc.update(kw)
	return doc


def _crop_figures(doc):
	return {
		c.crop: (c.plant_count, round(c.total_qty_kg, 6), c.total_bags, round(c.total_cost, 6))
		for c in doc.crops
	}


def _rows(doc, crop):
	no = next(c.crop_no for c in doc.crops if c.crop == crop)
	return [r for r in doc.fertilizers if r.crop_no == no]


class TestMultiCrop(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.customer = _customer()

	# 1, 14 ──────────────────────────────────────────────────────────
	def test_single_crop_recommendation(self):
		doc = frappe.get_doc(
			{
				"doctype": BASAL,
				"customer": self.customer,
				"first_name": "Ramesh",
				"mobile_no": MOBILE,
				"crops": [_crop(1, "Mango")],
				"fertilizers": _template(1, "Mango"),
			}
		).insert()
		self.assertTrue(doc.name.startswith("BDR-"))
		self.assertEqual(len(doc.crops), 1)
		self.assertAlmostEqual(doc.grand_total, doc.crops[0].total_cost)
		self.assertAlmostEqual(doc.crops[0].total_cost, sum(r.amount for r in doc.fertilizers))

	# 2, 5, 6 ────────────────────────────────────────────────────────
	def test_three_crops_one_recommendation(self):
		doc = _three_crops(self.customer).insert()
		self.assertEqual(
			[(c.crop_no, c.crop) for c in doc.crops], [(1, "Mango"), (2, "Banana"), (3, "Papaya")]
		)
		self.assertEqual(frappe.db.count(BASAL, {"name": doc.name}), 1)
		for c in doc.crops:
			rows = _rows(doc, c.crop)
			self.assertTrue(rows, c.crop)
			self.assertAlmostEqual(c.total_cost, sum(r.amount for r in rows), msg=c.crop)
			self.assertAlmostEqual(c.total_qty_kg, sum(r.qty_kg for r in rows), msg=c.crop)
			self.assertAlmostEqual(c.total_bags, sum(r.bags for r in rows), msg=c.crop)
			for r in rows:  # every row uses its own crop's plant count
				self.assertAlmostEqual(r.qty_kg, r.rate_gm * c.plant_count / 1000)
		self.assertAlmostEqual(doc.grand_total, sum(c.total_cost for c in doc.crops))
		self.assertAlmostEqual(doc.total_plants, sum(c.plant_count for c in doc.crops))

	# 3 ──────────────────────────────────────────────────────────────
	def test_area_change_affects_only_that_crop(self):
		base = _three_crops(self.customer).insert()
		bigger = _three_crops(self.customer)
		bigger.crops[0].area = 2  # Mango only
		bigger.insert()
		before, after = _crop_figures(base), _crop_figures(bigger)
		self.assertGreater(after["Mango"][0], before["Mango"][0])
		self.assertEqual(after["Banana"], before["Banana"])
		self.assertEqual(after["Papaya"], before["Papaya"])

	# 4 ──────────────────────────────────────────────────────────────
	def test_fertilizer_change_affects_only_that_crop(self):
		doc = _three_crops(self.customer).insert()
		before = _crop_figures(doc)
		mango_rows = [(r.name, r.qty_kg, r.amount) for r in _rows(doc, "Mango")]
		_rows(doc, "Banana")[0].rate = 90
		doc.save()
		after = _crop_figures(doc)
		self.assertNotEqual(after["Banana"], before["Banana"])
		self.assertEqual(after["Mango"], before["Mango"])
		self.assertEqual(after["Papaya"], before["Papaya"])
		self.assertEqual([(r.name, r.qty_kg, r.amount) for r in _rows(doc, "Mango")], mango_rows)

	def test_variety_belongs_to_its_own_crop(self):
		doc = _three_crops(self.customer)
		kesar = frappe.db.get_value("Farm Crop Variety", {"crop": "Mango", "used_in_basal": 1})
		doc.crops[0].variety = kesar
		doc.insert()
		self.assertEqual([c.variety or None for c in doc.crops], [kesar, None, None])
		bad = _three_crops(self.customer)
		bad.crops[1].variety = kesar  # a Mango variety on the Banana crop
		self.assertRaises(frappe.ValidationError, bad.insert)

	# 7, 8 ───────────────────────────────────────────────────────────
	def test_purchase_summary_combines_only_compatible_lines(self):
		doc = _three_crops(self.customer).insert()
		first = _rows(doc, "Mango")[0]
		banana = _rows(doc, "Banana")[0]
		lines = [p for p in doc.purchase_items if p.fertilizer_name == first.fertilizer_name]
		self.assertEqual(len(lines), 1)  # same fertilizer and pack in Mango and Banana
		self.assertAlmostEqual(lines[0].qty_kg, first.qty_kg + banana.qty_kg)
		self.assertAlmostEqual(lines[0].amount, first.amount + banana.amount)
		# the crop rows keep their own quantities
		self.assertNotAlmostEqual(first.qty_kg, lines[0].qty_kg)

		# the same fertilizer in different packs is never merged
		packs = {}
		for r in doc.fertilizers:
			packs.setdefault(r.fertilizer_name, set()).add(flt(r.pack_kg))
		for p in doc.purchase_items:
			self.assertIn(flt(p.pack_kg), packs[p.fertilizer_name])
		keys = [(p.fertilizer_name, flt(p.pack_kg)) for p in doc.purchase_items]
		self.assertEqual(len(keys), len(set(keys)))
		self.assertEqual(
			len(doc.purchase_items), len({(r.fertilizer_name, flt(r.pack_kg)) for r in doc.fertilizers})
		)

		# the purchase list is a regrouping, not an extra cost
		self.assertAlmostEqual(sum(p.amount for p in doc.purchase_items), doc.grand_total)

	def test_rate_units_are_converted_before_combining(self):
		doc = _three_crops(self.customer)
		mango, banana = _rows(doc, "Mango")[0], _rows(doc, "Banana")[0]
		banana.rate, banana.rate_unit = 0.05, "kg / plant"  # 50 gm per plant, written in kg
		doc.insert()
		self.assertAlmostEqual(banana.rate_gm, 50)
		line = next(p for p in doc.purchase_items if p.fertilizer_name == mango.fertilizer_name)
		self.assertAlmostEqual(line.qty_kg, mango.qty_kg + banana.qty_kg)

	def test_preview_matches_save(self):
		doc = _three_crops(self.customer)
		data = doc.as_dict(convert_dates_to_str=True)
		data["__islocal"] = 1
		for i, r in enumerate(data["crops"] + data["fertilizers"]):
			r["name"] = f"row-{i}"
		out = api.preview_basal_dose(json.dumps(data, default=str))
		doc.insert()
		self.assertAlmostEqual(out["parent"]["grand_total"], doc.grand_total)
		self.assertEqual(
			sorted(round(v["total_cost"], 6) for v in out["crops"].values()),
			sorted(round(c.total_cost, 6) for c in doc.crops),
		)

	# 9 ──────────────────────────────────────────────────────────────
	def test_removing_a_crop_leaves_the_others_unchanged(self):
		doc = _three_crops(self.customer).insert()
		before = _crop_figures(doc)
		papaya_rows = [(r.fertilizer_name, r.qty_kg, r.amount) for r in _rows(doc, "Papaya")]
		banana_no = next(c.crop_no for c in doc.crops if c.crop == "Banana")
		doc.crops = [c for c in doc.crops if c.crop != "Banana"]
		doc.fertilizers = [r for r in doc.fertilizers if r.crop_no != banana_no]
		doc.save()
		after = _crop_figures(doc)
		self.assertEqual(set(after), {"Mango", "Papaya"})
		self.assertEqual(after["Mango"], before["Mango"])
		self.assertEqual(after["Papaya"], before["Papaya"])
		self.assertEqual([c.crop_no for c in doc.crops], [1, 2])  # renumbered
		self.assertEqual([(r.fertilizer_name, r.qty_kg, r.amount) for r in _rows(doc, "Papaya")], papaya_rows)
		self.assertAlmostEqual(doc.grand_total, before["Mango"][3] + before["Papaya"][3])

	def test_rows_of_a_removed_crop_are_never_moved_to_another_crop(self):
		doc = _three_crops(self.customer).insert()
		doc.crops = [c for c in doc.crops if c.crop != "Banana"]  # its rows left behind
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		self.assertEqual(len(doc.crops), 3)

		dup = _three_crops(self.customer)
		dup.crops[2].crop_no = 1  # two crops claim number 1
		self.assertRaises(frappe.ValidationError, dup.insert)

	# 10, 11 ─────────────────────────────────────────────────────────
	def test_dashboard_tabs_show_each_crop_once(self):
		before = {t["crop"]: t["count"] for t in page.get_overview()["tabs"]}
		total_before = page.get_overview()["totals"]["count"]
		doc = _three_crops(self.customer).insert()
		overview = page.get_overview()
		after = {t["crop"]: t["count"] for t in overview["tabs"]}
		expected = {"Mango": 1, "Banana": 1, "Papaya": 1, "Guava": 0, "Pomegranate": 0}
		self.assertEqual({c: after[c] - before[c] for c in after}, expected)
		self.assertEqual(overview["totals"]["count"], total_before + 1)

		for c in doc.crops:
			res = page.get_crop_recommendations(c.crop, search=doc.name)
			self.assertEqual([r["name"] for r in res["rows"]], [doc.name])
			self.assertEqual(res["total"], 1)
			# the crop's own figures, not the recommendation's
			row = res["rows"][0]
			self.assertEqual(row["plants"], fmt(c.plant_count, 0))
			self.assertEqual(row["area"], f"{fmt(c.area)} {c.area_unit}")
			self.assertEqual(row["crop_cost"], inr0(c.total_cost))
			self.assertEqual(row["grand_total"], inr0(doc.grand_total))
		for crop in ("Guava", "Pomegranate"):
			self.assertEqual(page.get_crop_recommendations(crop, search=doc.name)["total"], 0)

	# 12 ─────────────────────────────────────────────────────────────
	def test_reports_do_not_double_count(self):
		# a farmer of its own: records saved by earlier tests in this class are still there
		farmer = create_customer(first_name="Report Farmer", mobile_no="9876500066")["customer"]
		doc = _three_crops(farmer, mobile_no="9876500066").insert()
		mine = {"customer": farmer}
		summary = fertilizer_requirement_summary.execute
		combined = summary(mine)[1]
		by_crop = summary({**mine, "group_by_crop": 1})[1]
		self.assertAlmostEqual(sum(r["amount"] for r in combined), doc.grand_total)
		self.assertAlmostEqual(sum(r["amount"] for r in by_crop), doc.grand_total)
		for c in doc.crops:
			own = [r for r in by_crop if r["crop"] == c.crop]
			self.assertAlmostEqual(sum(r["amount"] for r in own), c.total_cost, msg=c.crop)
			only = summary({**mine, "crop": c.crop})[1]
			self.assertAlmostEqual(sum(r["amount"] for r in only), c.total_cost, msg=c.crop)
		self.assertEqual(summary(mine)[0][0]["fieldname"], "fertilizer_name")  # default view unchanged
		self.assertEqual(summary({**mine, "group_by_crop": 1})[0][0]["fieldname"], "crop")

		register = basal_dose_register.execute(mine)[1]
		self.assertEqual([r.name for r in register].count(doc.name), 1)
		mine_row = next(r for r in register if r.name == doc.name)
		self.assertAlmostEqual(mine_row.grand_total, doc.grand_total)
		self.assertEqual(mine_row.crops, "Mango, Banana, Papaya")
		self.assertEqual(
			[r.name for r in basal_dose_register.execute({**mine, "crop": "Banana"})[1]], [doc.name]
		)

	# 13 ─────────────────────────────────────────────────────────────
	def test_print_has_a_section_per_crop(self):
		doc = _three_crops(self.customer).insert()
		html = frappe.get_print(BASAL, doc.name, PRINT_FORMAT, doc=doc)
		starts = [html.index(f"{c.crop} — Crop Recommendation") for c in doc.crops]
		self.assertEqual(starts, sorted(starts))
		purchase = html.index("Combined Fertilizer Purchase Summary")
		total = html.index("Total Recommendation Cost")
		self.assertLess(starts[-1], purchase)
		self.assertLess(purchase, total)
		sections = [html[a:b] for a, b in zip(starts, [*starts[1:], purchase], strict=True)]
		for c, section in zip(doc.crops, sections, strict=True):
			self.assertIn(f"{c.crop} subtotal", section)
			rows = _rows(doc, c.crop)
			# one fertilizer table per crop with exactly that crop's rows
			self.assertEqual(len(re.findall(r"<tr><td>\d+</td>", section)), len(rows), c.crop)
			for r in rows:
				self.assertIn(frappe.utils.escape_html(r.fertilizer_name), section)
		self.assertIn("TOTAL RECOMMENDATION COST (3 crops)", html)
		self.assertIn("agrismart_logo", html)
		self.assertNotRegex(html, "[\u0900-\u097f]")

	# 15 ─────────────────────────────────────────────────────────────
	def test_saved_recommendations_stay_readable_and_unchanged(self):
		_three_crops(self.customer).insert()
		for name in frappe.get_all(BASAL, pluck="name", order_by="creation desc", limit=20):
			doc = frappe.get_doc(BASAL, name)
			stored = (doc.grand_total, [(c.crop, c.total_cost) for c in doc.crops])
			apply_basal_calculation(doc)  # in memory only; nothing is saved
			self.assertAlmostEqual(doc.grand_total, stored[0], msg=name)
			for c, (crop, cost) in zip(doc.crops, stored[1], strict=True):
				self.assertAlmostEqual(c.total_cost, cost, msg=f"{name} {crop}")
			frappe.get_print(BASAL, name, PRINT_FORMAT, doc=frappe.get_doc(BASAL, name))

	# 16 ─────────────────────────────────────────────────────────────
	def test_permissions_still_apply(self):
		other = create_customer(first_name="Other Farmer", mobile_no="9876500055")["customer"]
		doc = _three_crops(self.customer).insert()
		theirs = _three_crops(other, first_name="Other", mobile_no="9876500055").insert()

		def user(email, roles):
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": "Test",
						"send_welcome_email": 0,
						"roles": [{"role": r} for r in roles],
					}
				).insert()
			return email

		nobody = user("fa-mc-nobody@example.com", [])
		advisor = user("fa-mc-advisor@example.com", ["Farm Advisor"])
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": advisor,
				"allow": "Customer",
				"for_value": other,
				"apply_to_all_doctypes": 1,
			}
		).insert()
		try:
			frappe.set_user(nobody)
			self.assertFalse(frappe.has_permission(BASAL, "read", doc))
			self.assertRaises(
				frappe.PermissionError, frappe.get_doc(BASAL, doc.name).check_permission, "read"
			)
			frappe.set_user(advisor)
			self.assertFalse(frappe.has_permission(BASAL, "read", doc))
			self.assertFalse(frappe.has_permission(BASAL, "write", doc))
			self.assertTrue(frappe.has_permission(BASAL, "read", theirs))
			self.assertEqual(
				[r["name"] for r in page.get_crop_recommendations("Banana", search=theirs.name)["rows"]],
				[theirs.name],
			)
			self.assertEqual(page.get_crop_recommendations("Banana", search=doc.name)["total"], 0)
		finally:
			frappe.set_user("Administrator")
