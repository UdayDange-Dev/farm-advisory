"""Basal fertilizer templates: create, edit, delete, validate, permissions and Load Template.

The values below are test inputs typed in as an administrator would, not
agronomic recommendations; every test is rolled back.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from farm_advisory import api
from farm_advisory.farm_advisory.doctype.farm_crop import farm_crop as templates
from farm_advisory.tests.test_integration import MOBILE, _customer

BASAL = "Basal Dose Recommendation"


def _rows():
	"""Two rows for an empty crop: one with its own pack and price, one using the master."""
	first, second = frappe.get_all(
		"Farm Fertilizer", filters={"is_active": 1}, pluck="name", order_by="name asc", limit=2
	)
	return [
		{"fertilizer": first, "rate": 40, "rate_unit": "gm / plant", "pack_kg": 10, "cost_per_bag": 500},
		{"fertilizer": second, "rate": 0.02, "rate_unit": "kg / plant", "pack_kg": 0, "cost_per_bag": 0},
	]


def _user(email, roles):
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


class TestFertilizerTemplates(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.crop = next(
			c["crop"] for c in templates.get_template_overview()["crops"] if not c["fertilizers"]
		)  # a Basal crop without a template (Banana or Guava)

	def tearDown(self):
		# each test starts from the real templates, not from what an earlier test saved
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_overview_lists_crops_with_and_without_templates(self):
		overview = templates.get_template_overview()
		by_crop = {c["crop"]: c["fertilizers"] for c in overview["crops"]}
		self.assertTrue(overview["can_write"])
		self.assertEqual(by_crop[self.crop], [])
		self.assertTrue(by_crop["Mango"])
		basal = set(frappe.get_all("Farm Crop", {"used_in_basal": 1}, pluck="name"))
		self.assertEqual(set(by_crop), basal)

	def test_create_then_load_into_a_recommendation(self):
		rows = _rows()
		saved = templates.save_template(self.crop, rows)
		self.assertEqual([r["fertilizer"] for r in saved["rows"]], [r["fertilizer"] for r in rows])

		# available to Load Template at once, with 0 falling back to the master
		tpl = api.get_crop_defaults(self.crop)["template"]
		master = frappe.db.get_value(
			"Farm Fertilizer", rows[1]["fertilizer"], ["pack_kg", "cost_per_bag"], as_dict=True
		)
		self.assertEqual((tpl[0]["pack_kg"], tpl[0]["cost_per_bag"]), (10, 500))
		self.assertEqual((tpl[1]["pack_kg"], tpl[1]["cost_per_bag"]), (master.pack_kg, master.cost_per_bag))

		# loaded into crop 2 of a two-crop recommendation, it is calculated for that crop only
		mango = api.get_crop_defaults("Mango")
		doc = frappe.get_doc(
			{
				"doctype": BASAL,
				"customer": _customer(),
				"first_name": "Ramesh",
				"mobile_no": MOBILE,
				"crops": [
					{"crop_no": 1, "crop": "Mango", "row_spacing": 15, "plant_spacing": 15, "area": 1},
					{"crop_no": 2, "crop": self.crop, "row_spacing": 6, "plant_spacing": 6, "area": 1},
				],
				"fertilizers": [
					*({**t, "crop_no": 1} for t in mango["template"]),
					*({**t, "crop_no": 2} for t in tpl),
				],
			}
		).insert()
		crop2 = doc.crops[1]
		own = [r for r in doc.fertilizers if r.crop_no == 2]
		self.assertEqual(len(own), 2)
		self.assertAlmostEqual(own[1].rate_gm, 20)  # 0.02 kg per plant
		self.assertAlmostEqual(own[0].qty_kg, 40 * crop2.plant_count / 1000)
		self.assertAlmostEqual(crop2.total_cost, sum(r.amount for r in own))
		self.assertAlmostEqual(doc.grand_total, sum(c.total_cost for c in doc.crops))
		self.assertTrue(any(p.fertilizer_name == own[0].fertilizer_name for p in doc.purchase_items))

	def test_edit_keeps_unchanged_values(self):
		before = templates.get_template("Mango")["rows"]
		rows = [{k: r[k] for k in templates.TEMPLATE_FIELDS} for r in before]
		rows[0]["rate"] = 55
		after = templates.save_template("Mango", rows)["rows"]
		self.assertEqual(after[0]["rate"], 55)
		for b, a in zip(before[1:], after[1:], strict=True):
			self.assertEqual(
				{k: b[k] for k in templates.TEMPLATE_FIELDS}, {k: a[k] for k in templates.TEMPLATE_FIELDS}
			)
		# 0 pack / price stays 0, so the row keeps following the master
		self.assertEqual(flt(after[0]["pack_kg"]), flt(before[0]["pack_kg"]))

	def test_delete_template(self):
		templates.save_template(self.crop, _rows())
		templates.delete_template(self.crop)
		self.assertEqual(templates.get_template(self.crop)["rows"], [])
		self.assertEqual(api.get_crop_defaults(self.crop)["template"], [])
		self.assertTrue(frappe.db.exists("Farm Crop", self.crop))  # the crop itself is kept

	def test_validation(self):
		def bad(**change):
			rows = _rows()
			rows[0].update(change)
			self.assertRaises(frappe.ValidationError, templates.save_template, self.crop, rows)

		bad(rate=0)
		bad(rate=-5)
		bad(rate_unit="litre / plant")
		bad(rate_unit="")
		bad(pack_kg=-1)
		bad(cost_per_bag=-10)
		bad(fertilizer="NO SUCH FERTILIZER")
		bad(fertilizer="")
		bad(unexpected="x")
		self.assertRaises(frappe.ValidationError, templates.save_template, self.crop, [])
		self.assertRaises(frappe.ValidationError, templates.save_template, self.crop, "not a list")
		twice = _rows()
		twice[1]["fertilizer"] = twice[0]["fertilizer"]
		self.assertRaises(frappe.ValidationError, templates.save_template, self.crop, twice)
		self.assertRaises(frappe.DoesNotExistError, templates.save_template, "No Such Crop", _rows())
		self.assertEqual(templates.get_template(self.crop)["rows"], [])  # nothing was saved

	def test_missing_pack_or_price_must_be_entered(self):
		f = frappe.get_doc(
			{
				"doctype": "Farm Fertilizer",
				"fertilizer_name": "TEST UNPRICED",
				"pack_kg": 25,
				"cost_per_bag": 0,
			}
		).insert()
		row = {"fertilizer": f.name, "rate": 10, "rate_unit": "gm / plant", "pack_kg": 0, "cost_per_bag": 0}
		with self.assertRaisesRegex(frappe.ValidationError, "bag price"):
			templates.save_template(self.crop, [row])
		templates.save_template(self.crop, [{**row, "cost_per_bag": 700}])  # entered explicitly
		self.assertEqual(api.get_crop_defaults(self.crop)["template"][0]["cost_per_bag"], 700)

	def test_inactive_fertilizer_only_blocks_new_rows(self):
		templates.save_template(self.crop, _rows())
		first = _rows()[0]["fertilizer"]
		frappe.db.set_value("Farm Fertilizer", first, "is_active", 0)
		# an unchanged row keeps saving after its fertilizer is deactivated
		kept = [
			{k: r[k] for k in templates.TEMPLATE_FIELDS} for r in templates.get_template(self.crop)["rows"]
		]
		doc = frappe.get_doc("Farm Crop", self.crop)
		doc.default_row_spacing = doc.default_row_spacing
		doc.save()
		# but it cannot be added to another template
		other = next(c["crop"] for c in templates.get_template_overview()["crops"] if not c["fertilizers"])
		self.assertRaises(frappe.ValidationError, templates.save_template, other, [kept[0]])

	def test_existing_templates_pass_the_new_validation(self):
		for crop in frappe.get_all("Farm Crop", {"used_in_basal": 1}, pluck="name"):
			doc = frappe.get_doc("Farm Crop", crop)
			doc.validate_fertilizer_template()  # raises if a saved template is now invalid

	def test_permissions(self):
		advisor = _user("fa-tpl-advisor@example.com", ["Farm Advisor"])
		nobody = _user("fa-tpl-nobody@example.com", [])
		try:
			frappe.set_user(advisor)  # Farm Advisor: read only on Farm Crop
			self.assertFalse(templates.get_template_overview()["can_write"])
			self.assertTrue(templates.get_template("Mango")["rows"])
			self.assertRaises(frappe.PermissionError, templates.save_template, self.crop, _rows())
			self.assertRaises(frappe.PermissionError, templates.delete_template, "Mango")
			frappe.set_user(nobody)
			self.assertRaises(frappe.PermissionError, templates.get_template_overview)
			self.assertRaises(frappe.PermissionError, templates.get_template, "Mango")
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(templates.get_template("Mango")["rows"])  # untouched
