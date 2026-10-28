"""Basal Dose page data, report filters and the form layout, on a real site."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from farm_advisory.farm_advisory.page.basal_dose import basal_dose as page
from farm_advisory.farm_advisory.report.basal_dose_register import basal_dose_register
from farm_advisory.farm_advisory.report.fertilizer_requirement_summary import fertilizer_requirement_summary
from farm_advisory.tests.test_integration import MOBILE, _basal, _customer
from farm_advisory.utils.farmer import create_customer

BASAL = "Basal Dose Recommendation"
DEVANAGARI = "[\u0900-\u097f]"


def _user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
				"roles": [{"role": r} for r in roles],
			}
		).insert()
	return email


def _tab(overview, crop):
	return next(t for t in overview["tabs"] if t["crop"] == crop)


def _names(crop, **kw):
	return [r["name"] for r in page.get_crop_recommendations(crop, page_length=100, **kw)["rows"]]


class TestBasalDosePage(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.customer = _customer()

	def _mango_banana(self, customer=None, **kw):
		"""A Mango (template) + Banana (no template, no fertilizer rows) recommendation."""
		doc = _basal(customer or self.customer)
		doc.append(
			"crops",
			{
				"crop_no": 2,
				"crop": "Banana",
				"row_spacing": 6,
				"plant_spacing": 5,
				"spacing_unit": "Feet",
				"area": 10,
				"area_unit": "Guntha",
			},
		)
		doc.update(kw)
		return doc.insert()

	def test_overview_counts_each_crop_once(self):
		before = page.get_overview()
		doc = self._mango_banana()
		twice = _basal(self.customer)  # two Mango rows in one recommendation
		mango = twice.crops[0]
		twice.append(
			"crops",
			{
				"crop_no": 2,
				"crop": "Mango",
				"row_spacing": mango.row_spacing,
				"plant_spacing": mango.plant_spacing,
				"spacing_unit": "Feet",
				"area": 1,
				"area_unit": "Acre",
			},
		)
		twice.insert()

		after = page.get_overview()
		self.assertEqual(after["totals"]["count"], before["totals"]["count"] + 2)
		expected = {"Mango": 2, "Banana": 1, "Guava": 0, "Papaya": 0, "Pomegranate": 0}
		for crop, delta in expected.items():
			self.assertEqual(_tab(after, crop)["count"], _tab(before, crop)["count"] + delta, crop)
		self.assertEqual(
			[t["crop"] for t in after["tabs"]], ["Pomegranate", "Banana", "Guava", "Mango", "Papaya"]
		)
		# Banana and Guava have no template in the prototype; none is invented
		self.assertFalse(_tab(after, "Banana")["has_template"])
		self.assertFalse(_tab(after, "Guava")["has_template"])
		self.assertTrue(_tab(after, "Mango")["has_template"])
		recent = {r["name"]: r for r in after["recent"]}
		self.assertIn(doc.name, recent)
		self.assertEqual(recent[doc.name]["crops"], "Mango, Banana")
		self.assertTrue(after["fertilizers"])

	def test_crop_tab_lists_only_that_crop(self):
		doc = self._mango_banana()
		mango_only = _basal(self.customer).insert()

		self.assertIn(doc.name, _names("Banana"))
		self.assertNotIn(mango_only.name, _names("Banana"))
		self.assertTrue({doc.name, mango_only.name} <= set(_names("Mango")))
		self.assertNotIn(doc.name, _names("Guava"))

		row = next(r for r in page.get_crop_recommendations("Banana")["rows"] if r["name"] == doc.name)
		# the Banana row's own figures, not the Mango row's
		self.assertEqual(row["area"], "10 Guntha")
		self.assertEqual(row["plants"], str(doc.crops[1].plant_count))
		self.assertEqual(row["farmer_name"], "Ramesh Patil")

		for crop in page.CROP_TABS:
			for name in _names(crop):
				self.assertTrue(frappe.db.exists("Basal Dose Crop", {"parent": name, "crop": crop}), crop)

	def test_crop_tab_search_dates_and_paging(self):
		doc = self._mango_banana()
		self.assertIn(doc.name, _names("Banana", search="Ramesh"))
		self.assertIn(doc.name, _names("Banana", search=MOBILE[-4:]))
		self.assertIn(doc.name, _names("Banana", search=doc.name))
		self.assertNotIn(doc.name, _names("Banana", search="no-such-farmer-xyz"))
		self.assertIn(doc.name, _names("Banana", from_date=today(), to_date=today()))
		self.assertNotIn(doc.name, _names("Banana", from_date=add_days(today(), 1)))
		self.assertNotIn(doc.name, _names("Banana", village="No Such Village"))

		self._mango_banana()
		first = page.get_crop_recommendations("Banana", page_length=1)
		second = page.get_crop_recommendations("Banana", start=1, page_length=1)
		self.assertEqual(len(first["rows"]), 1)
		self.assertGreaterEqual(first["total"], 2)
		self.assertNotEqual(first["rows"][0]["name"], second["rows"][0]["name"])
		capped = page.get_crop_recommendations("Banana", page_length=10_000)
		self.assertEqual(capped["page_length"], page.MAX_PAGE_LENGTH)

	def test_crop_tab_rejects_bad_input(self):
		self.assertRaises(frappe.ValidationError, page.get_crop_recommendations, "Not A Crop")
		self.assertRaises(
			frappe.ValidationError, page.get_crop_recommendations, "Mango", from_date="31-31-2026"
		)
		# search text is bound as a value, never spliced into SQL
		self.assertEqual(page.get_crop_recommendations("Mango", search="' OR 1=1 -- ")["total"], 0)

	def test_permissions(self):
		other = create_customer(first_name="Other Farmer", mobile_no="9876500044")["customer"]
		self._mango_banana()
		mine = self._mango_banana(other, first_name="Other", mobile_no="9876500044")

		nobody = _user("fa-no-access@example.com", [])
		advisor = _user("fa-limited-advisor@example.com", ["Farm Advisor"])
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
			self.assertRaises(frappe.PermissionError, page.get_overview)
			self.assertRaises(frappe.PermissionError, page.get_crop_recommendations, "Mango")

			frappe.set_user(advisor)
			overview = page.get_overview()
			self.assertEqual(overview["totals"]["count"], 1)
			self.assertEqual(_tab(overview, "Banana")["count"], 1)
			self.assertEqual([r["name"] for r in overview["recent"]], [mine.name])
			self.assertEqual(_names("Mango"), [mine.name])
		finally:
			frappe.set_user("Administrator")

	def test_report_crop_and_fertilizer_filters(self):
		doc = self._mango_banana()
		summary = fertilizer_requirement_summary.execute
		mine = {"customer": self.customer}
		self.assertEqual(summary({**mine, "crop": "Mango"})[1], summary(mine)[1])
		# the Banana crop of this record has no fertilizer rows
		self.assertEqual(summary({**mine, "crop": "Banana"})[1], [])
		first = doc.fertilizers[0]
		rows = summary({**mine, "fertilizer": first.fertilizer})[1]
		self.assertEqual({r["fertilizer_name"] for r in rows}, {first.fertilizer_name})

		names = lambda crop: [d.name for d in basal_dose_register.execute({**mine, "crop": crop})[1]]  # noqa: E731
		self.assertIn(doc.name, names("Banana"))
		self.assertNotIn(doc.name, names("Guava"))
		columns = basal_dose_register.execute({})[0]
		self.assertEqual(next(c["label"] for c in columns if c["fieldname"] == "farmer_name"), "Farmer")

	def test_redesigned_ui_is_english_only(self):
		self._mango_banana()
		surfaces = {
			"page overview": page.get_overview(),
			"crop tab": page.get_crop_recommendations("Banana"),
			"basal form labels": [f.label for f in frappe.get_meta(BASAL).fields],
			"page title": frappe.db.get_value("Page", "basal-dose", "title"),
			"workspace": frappe.get_doc("Workspace", "Farm Advisory").as_dict(),
			"sidebar": frappe.get_doc("Sidebar", "Farm Advisory").as_dict(),
			"number cards": frappe.get_all("Number Card", {"module": "Farm Advisory"}, ["label"]),
			"charts": frappe.get_all("Dashboard Chart", {"module": "Farm Advisory"}, ["chart_name"]),
		}
		for report in (basal_dose_register, fertilizer_requirement_summary):
			surfaces[report.__name__] = report.execute({})[0]
		for name, value in surfaces.items():
			self.assertNotRegex(frappe.as_json(value, ensure_ascii=False), DEVANAGARI, name)

	def test_form_has_no_print_section(self):
		meta = frappe.get_meta(BASAL)
		self.assertFalse(meta.get_field("recommendation_preview"))
		self.assertFalse(meta.get_field("report_tab"))
		# the only HTML field is the crop-wise editor, which is not the print layout
		self.assertEqual([f.fieldname for f in meta.fields if f.fieldtype == "HTML"], ["crop_cards"])
		self.assertEqual(meta.default_print_format, "Basal Dose Recommendation Report")
		doc = self._mango_banana()
		html = frappe.get_print(BASAL, doc.name, "Basal Dose Recommendation Report", doc=doc)
		for text in ("Fertilizer Basal Dose Recommendation", "Ramesh Patil", "Banana", "Mango"):
			self.assertIn(text, html)
