"""Save, validation, preview, print, share and report paths on a real site."""

import csv
import io
import json

import frappe
from frappe.tests import IntegrationTestCase

from farm_advisory import api
from farm_advisory.utils.farmer import create_customer, get_farmer_details
from farm_advisory.utils.share import basal_csv

MOBILE = "9876500011"


def _customer():
	return create_customer(
		first_name="Ramesh",
		middle_name="Bhausaheb",
		last_name="Patil",
		mobile_no="+91 98765 00011",
		village="Loni",
		taluka="Sangamner",
		district="Ahilyanagar",
		state="Maharashtra",
		pin_code="422605",
	)["customer"]


def _spray(customer, **kw):
	doc = frappe.get_doc(
		{
			"doctype": "Spray Schedule",
			"customer": customer,
			"first_name": "Ramesh",
			"last_name": "Patil",
			"mobile_no": MOBILE,
			"whatsapp_same_as_mobile": 1,
			"crop": "Pomegranate",
			"plantation_date": "2024-06-01",
			"area": 1,
			"area_unit": "Acre",
			"spacing_unit": "Feet",
			"row_spacing": 12,
			"plant_spacing": 9,
			"water_basis": "Litres per acre",
			"water_value": 200,
			"spray_equipment": "HTP Pump",
			"tank_capacity": 200,
			"sprays": [{"spray_no": 1, "spray_date": "2026-03-10"}, {"spray_no": 2}],
			"products": [
				{
					"spray_no": 1,
					"category": "Insecticides",
					"product": "Delegate",
					"dose": 0.5,
					"dose_unit": "ml / L",
					"rate": 1200,
				},
				{
					"spray_no": 1,
					"category": "Fungicides",
					"product": "M-45",
					"dose": 2.5,
					"dose_unit": "gm / L",
					"rate": 600,
				},
				{
					"spray_no": 2,
					"category": "Fungicides",
					"product": "Bavistin",
					"dose": 500,
					"dose_unit": "ppm (mg/L)",
					"rate": 900,
				},
			],
		}
	)
	doc.update(kw)
	return doc


def _basal(customer):
	d = api.get_crop_defaults("Mango")
	return frappe.get_doc(
		{
			"doctype": "Basal Dose Recommendation",
			"customer": customer,
			"first_name": "Ramesh",
			"last_name": "Patil",
			"mobile_no": MOBILE,
			"whatsapp_same_as_mobile": 1,
			"bag_rounding": "Round up (full bags)",
			"crops": [
				{
					"crop_no": 1,
					"crop": "Mango",
					"row_spacing": d["row_spacing"],
					"plant_spacing": d["plant_spacing"],
					"spacing_unit": "Feet",
					"area": 1,
					"area_unit": "Acre",
				}
			],
			"fertilizers": [{**t, "crop_no": 1} for t in d["template"]],
		}
	)


class TestFarmAdvisory(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.customer = _customer()

	def test_customer_is_farmer_master(self):
		c = frappe.get_doc("Customer", self.customer)
		self.assertEqual(c.customer_name, "Ramesh Bhausaheb Patil")
		self.assertEqual((c.mobile_no, c.fa_village, c.fa_pin_code), (MOBILE, "Loni", "422605"))
		# same mobile → same Customer, never a duplicate farmer
		again = create_customer(first_name="R", mobile_no="09876500011")
		self.assertEqual(again, {"customer": self.customer, "existing": True})
		details = get_farmer_details(self.customer)
		self.assertEqual((details["first_name"], details["last_name"]), ("Ramesh", "Patil"))

	def test_spray_save_and_snapshot(self):
		doc = _spray(self.customer).insert()
		self.assertEqual(doc.farmer_name, "Ramesh Patil")
		self.assertEqual(doc.plant_count, 403)
		self.assertEqual((doc.total_water, doc.tank_loads), (200, 1))
		self.assertEqual(doc.crop_age_days, 647)
		self.assertIn("1 yr / वर्ष 9 mo / महिने 9 days / दिवस", doc.crop_age)
		delegate, m45, bav = doc.products
		self.assertEqual(
			(delegate.total_qty, delegate.base_unit, delegate.pack_suggestion), (100, "ml", "1 × 100 ml")
		)
		self.assertEqual((m45.total_qty, m45.base_unit), (500, "gm"))
		self.assertEqual((bav.total_qty, bav.base_unit), (100, "gm"))  # 500 mg/L × 200 L
		self.assertEqual(delegate.product_name_mr, "डेलीगेट")
		self.assertAlmostEqual(doc.sprays[0].spray_total, 0.1 * 1200 + 0.5 * 600)
		self.assertAlmostEqual(doc.grand_total, 0.1 * 1200 + 0.5 * 600 + 0.1 * 900)

		# a later rename of the master does not rewrite the saved record
		frappe.db.set_value("Spray Product", "Delegate", "product_name_mr", "बदल")
		doc.reload()
		doc.save()
		self.assertEqual(doc.products[0].product_name_mr, "डेलीगेट")

	def test_spray_validation(self):
		bad = _spray(self.customer)
		bad.products[0].category = "Herbicides"  # Delegate is an insecticide
		self.assertRaises(frappe.ValidationError, bad.insert)
		orphan = _spray(self.customer)
		orphan.products[2].spray_no = 7
		self.assertRaises(frappe.ValidationError, orphan.insert)
		self.assertRaises(frappe.ValidationError, _spray(self.customer, mobile_no="12345").insert)

	def test_spray_renumbers_after_removal(self):
		doc = _spray(self.customer)
		doc.sprays = [doc.sprays[1]]
		doc.products = [doc.products[2]]
		doc.insert()
		self.assertEqual((doc.sprays[0].spray_no, doc.products[0].spray_no), (1, 1))

	def test_spray_preview_matches_save(self):
		doc = _spray(self.customer)
		data = doc.as_dict(convert_dates_to_str=True)
		data["__islocal"] = 1
		for i, r in enumerate(data["sprays"] + data["products"]):
			r["name"] = f"row-{i}"
		out = api.preview_spray_schedule(json.dumps(data, default=str))
		doc.insert()
		self.assertEqual(out["parent"]["grand_total"], doc.grand_total)
		self.assertEqual(out["parent"]["plant_count"], doc.plant_count)
		self.assertIn("डेलीगेट", out["html"])

	def test_spray_print_and_whatsapp(self):
		doc = _spray(self.customer, report_language="English + Marathi").insert()
		html = frappe.get_print("Spray Schedule", doc.name, "Spray Schedule Report", doc=doc)
		for s in ("AGRI SMART FARM SOLUTIONS LLP", "Delegate / डेलीगेट", "10-03-2026", "__ / __ / ____"):
			self.assertIn(s, html)
		msg = api.get_whatsapp_message("Spray Schedule", doc.name)
		self.assertEqual(msg["number"], "91" + MOBILE)
		self.assertIn("Ramesh Patil", msg["text"])

	def test_basal_mango_template(self):
		doc = _basal(self.customer).insert()
		crop = doc.crops[0]
		self.assertEqual(crop.plant_count, 193)
		names = [f.fertilizer_name for f in doc.fertilizers]
		self.assertEqual(names[0], "ORGANIC 4 G - NPK")
		self.assertEqual(len(names), 8)
		bio = doc.fertilizers[1]
		self.assertEqual((bio.pack_kg, bio.contains), (25, "BIO AVAILABLE PHOSPHORUS 10 %"))
		self.assertAlmostEqual(doc.grand_total, sum(f.amount for f in doc.fertilizers))
		self.assertAlmostEqual(crop.cost_per_plant, crop.total_cost / 193)
		self.assertEqual(len(doc.purchase_items), 8)
		frappe.get_print("Basal Dose Recommendation", doc.name, "Basal Dose Recommendation Report", doc=doc)

	def test_basal_two_crops_purchase_list(self):
		doc = _basal(self.customer)
		doc.append(
			"crops",
			{
				"crop_no": 2,
				"crop": "Mango",
				"row_spacing": 10,
				"plant_spacing": 10,
				"spacing_unit": "Feet",
				"area": 1,
				"area_unit": "Acre",
			},
		)
		doc.append(
			"fertilizers",
			{
				"crop_no": 2,
				"fertilizer": "MEGACAL",
				"fertilizer_name": "MEGACAL",
				"rate": 50,
				"rate_unit": "gm / plant",
				"pack_kg": 25,
				"cost_per_bag": 900,
			},
		)
		doc.insert()
		megacal = [p for p in doc.purchase_items if p.fertilizer_name == "MEGACAL"]
		self.assertEqual(len(megacal), 1)
		both = [f for f in doc.fertilizers if f.fertilizer_name == "MEGACAL"]
		self.assertAlmostEqual(megacal[0].qty_kg, sum(f.qty_kg for f in both))

	def test_basal_csv(self):
		doc = _basal(self.customer).insert()
		text = basal_csv(doc)
		self.assertTrue(text.startswith("﻿"))
		rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
		self.assertTrue(any("ORGANIC 4 G - NPK" in r for r in rows))
		self.assertIn("\r\n", text)

	def test_legacy_import(self):
		legacy = {
			"farmer": {
				"fn": "Sita",
				"ln": "More",
				"village": "Loni",
				"mobile": "9876500022",
				"wa": "9876500022",
			},
			"rnd": "near",
			"crops": [
				{
					"crop": "Mango",
					"variety": "Kesar",
					"rs": 15,
					"ps": 15,
					"su": "ft",
					"area": 2,
					"au": "acre",
					"plants": 0,
					"manual": False,
					"rows": [
						{"f": "MEGACAL", "pack": 25, "cost": 900, "rate": 50, "unit": "gm"},
						{"f": "", "rate": 0},
					],
				}
			],
		}
		v = api.import_legacy_basal_file(json.dumps(legacy))
		self.assertEqual(v["bag_rounding"], "Nearest bag (like Excel)")
		self.assertEqual(v["crops"][0]["variety"], "Mango - Kesar")
		self.assertEqual(len(v["fertilizers"]), 1)
		self.assertRaises(frappe.ValidationError, api.import_legacy_basal_file, "not json")

	def test_reports_run(self):
		_spray(self.customer).insert()
		_basal(self.customer).insert()
		for report in ("Spray Schedule Register", "Basal Dose Register", "Fertilizer Requirement Summary"):
			from frappe.desk.query_report import run

			result = run(report, filters={})
			self.assertTrue(result["result"], report)

	def test_advisor_permissions(self):
		email = "fa-advisor@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Advisor",
					"send_welcome_email": 0,
					"roles": [{"role": "Farm Advisor"}],
				}
			).insert()
		frappe.set_user(email)
		try:
			cust = create_customer(first_name="Advisor Farmer", mobile_no="9876500033")["customer"]
			doc = _spray(cust, mobile_no="9876500033").insert()
			self.assertTrue(frappe.has_permission("Spray Schedule", "print", doc))
			self.assertFalse(frappe.has_permission("Spray Schedule", "delete", doc))
			self.assertFalse(frappe.has_permission("Farm Advisory Settings", "write"))
			api.preview_basal_dose(
				json.dumps({**_basal(cust).as_dict(convert_dates_to_str=True), "__islocal": 1}, default=str)
			)
		finally:
			frappe.set_user("Administrator")
