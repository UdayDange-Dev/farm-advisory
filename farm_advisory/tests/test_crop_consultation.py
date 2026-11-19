"""Agrismart Crop Consultancy: engine, save / validation, preview, print, share, report,
and the ERPNext Address fetch shared with the Spray and Basal calculators."""

import json

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from farm_advisory import api
from farm_advisory.tests.test_integration import MOBILE, _basal, _customer, _spray
from farm_advisory.utils import consultation_calc as cc
from farm_advisory.utils import measure
from farm_advisory.utils.farmer import customer_address_query, get_address_display, get_farmer_details

CC = "Crop Consultation"


def _consultation(customer, **kw):
	doc = frappe.get_doc(
		{
			"doctype": CC,
			"customer": customer,
			"first_name": "Ramesh",
			"last_name": "Patil",
			"mobile_no": MOBILE,
			"whatsapp_same_as_mobile": 1,
			"visit_date": "2026-11-10",
			"latitude": 19.5761,
			"longitude": 74.2069,
			"farm_area_unit": "Acre",
			"total_area": 5,
			"irrigated_area": 4,
			"non_irrigated_area": 1,
			"dripper_lph": 4,
			"crop_blocks": [
				{
					"crop": "Pomegranate",
					"crop_stage": "Flowering",
					"plantation_date": "2024-06-01",
					"area": 1,
					"area_unit": "Acre",
					"row_spacing": 12,
					"plant_spacing": 9,
					"spacing_unit": "Feet",
				},
				{"crop": "Mango", "area": 40, "area_unit": "Guntha", "row_spacing": 15, "plant_spacing": 15},
			],
			"problems": [
				{
					"block_no": 1,
					"problem_type": "Physiological disorder",
					"affected_part": "Fruit",
					"severity": "High",
					"affected_pct": 12,
					"observation": "Fruit cracking after rain",
				}
			],
			"ndvi_readings": [
				{"reading_date": "2026-10-01", "ndvi": 0.62},
				{"reading_date": "2026-10-20", "ndvi": 0.52},
			],
			"irr_block_no": 1,
			"irr_drippers_per_plant": 2,
			"irr_hours": 2,
			"irr_required_per_plant": 20,
			"prescription_items": [
				{
					"category": "Micronutrient",
					"product": "Boron",
					"dose": 1,
					"dose_unit": "gm",
					"per": "L water",
				}
			],
		}
	)
	doc.update(kw)
	return doc


def _address(customer, title, primary=0, pincode="422605", city="Loni"):
	return frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Billing",
			"address_line1": f"{title}, Gat No. 12",
			"city": city,
			"county": "Sangamner",
			"state": "Maharashtra",
			"pincode": pincode,
			"country": "India",
			"is_primary_address": primary,
			"links": [{"link_doctype": "Customer", "link_name": customer}],
		}
	).insert(ignore_permissions=True)


class TestConsultationEngine(UnitTestCase):
	def _rows(self, *pairs):
		return [frappe._dict(reading_date=d, ndvi=v) for d, v in pairs]

	def test_ndvi_trend(self):
		# 0.62 → 0.52 is exactly a 0.10 drop: "stress", not lost to 0.0999999 float error
		self.assertEqual(
			cc.ndvi_status(self._rows(("2026-10-01", 0.62), ("2026-10-20", 0.52))),
			(0.52, -0.1, "Stress detected"),
		)
		self.assertEqual(
			cc.ndvi_status(self._rows(("2026-10-01", 0.60), ("2026-10-20", 0.56)))[2], "Moderate stress"
		)
		self.assertEqual(
			cc.ndvi_status(self._rows(("2026-10-01", 0.60), ("2026-10-20", 0.61)))[2], "Healthy / stable"
		)
		# order comes from the dates, not the rows; 0 = not entered
		self.assertEqual(
			cc.ndvi_status(self._rows(("2026-10-20", 0.52), ("2026-10-01", 0.62), ("2026-10-25", 0)))[2],
			"Stress detected",
		)
		self.assertEqual(cc.ndvi_status(self._rows(("2026-10-01", 0.6))), (0.6, None, ""))
		self.assertEqual(cc.ndvi_status([]), (None, None, ""))

	def test_spray_decision(self):
		self.assertEqual(cc.spray_decision(0, 0, 0, 0), ("", []))
		self.assertEqual(cc.spray_decision(10, 5, 60, 30)[0], "Suitable")
		self.assertEqual(cc.spray_decision(10, 5, 90, 30)[0], "Spray with caution")
		self.assertEqual(cc.spray_decision(40, 5, 90, 36)[0], "Do not spray")
		self.assertEqual(cc.spray_decision(0, 16, 0, 0)[0], "Do not spray")
		self.assertEqual(len(cc.spray_decision(40, 16, 85, 35)[1]), 4)

	def test_irrigation(self):
		block = frappe._dict(plant_count=400, area=1, area_unit="Acre")
		r = cc.irrigation(block, 4, 2, 0, 2, 20)
		self.assertEqual((r["drippers"], r["flow"], r["litres"], r["per_plant"]), (800, 3200, 6400, 16))
		self.assertAlmostEqual(r["depth"], 6400 / measure.SQ_M_PER_ACRE)
		self.assertEqual(r["status"], "Below requirement")  # 16 < 18 (= 20 × 0.9)
		self.assertEqual(cc.irrigation(block, 4, 2, 0, 2, 16)["status"], "Close to requirement")
		self.assertEqual(cc.irrigation(block, 4, 2, 0, 2, 14)["status"], "Above requirement")
		# total drippers are used when drippers / plant is blank
		self.assertEqual(cc.irrigation(block, 4, 0, 500, 1, 0)["litres"], 2000)
		self.assertEqual(cc.irrigation(None, 4, 2, 0, 2, 0)["litres"], 0)

	def test_satyukt_parse(self):
		out = cc.parse_satyukt(
			{
				"ndvi": [{"date": "2026-08-01", "v": 0.62}, {"date": "2026-08-15", "ndvi": 0.58, "blk": "A"}],
				"soil": {"n": "Low", "p": "Medium", "k": "Huge", "ph": 7.8},
				"moisture": "Medium",
				"pest": "Moderate",
				"weather": {"rain": 20, "wind": 8},
			}
		)
		v = out["values"]
		self.assertEqual(
			(v["soil_n"], v["soil_p"], v["soil_ph"], v["pest_risk"]), ("Low", "Medium", 7.8, "Moderate")
		)
		self.assertNotIn("soil_k", v)  # not a valid level
		self.assertEqual((v["rain_probability"], v["wind_speed"]), (20, 8))
		self.assertEqual(out["ndvi"][1], {"reading_date": "2026-08-15", "ndvi": 0.58, "crop_block": "A"})
		self.assertRaises(frappe.ValidationError, cc.parse_satyukt, [1, 2])

	def test_followups(self):
		self.assertEqual(
			[str(d) for _, d in cc.followup_dates("2026-11-10")],
			["2026-11-13", "2026-11-17", "2026-11-25", "2026-12-10"],
		)


class TestCropConsultation(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.customer = _customer()

	def test_save_calculates(self):
		doc = _consultation(self.customer).insert()
		self.assertTrue(doc.name.startswith("CCV-"))
		self.assertEqual(doc.farmer_name, "Ramesh Patil")
		b1, b2 = doc.crop_blocks
		self.assertEqual((b1.block_no, b2.block_no), (1, 2))
		self.assertEqual((b1.plant_count, b2.plant_count), (403, 194))
		self.assertAlmostEqual(b2.area_acre, 1, places=9)  # 40 guntha
		self.assertIn("days", b1.plant_age)
		self.assertAlmostEqual(doc.crop_area_total, 2, places=9)
		self.assertEqual(doc.total_plants, 597)
		self.assertEqual(doc.crop_summary, "Pomegranate, Mango")
		self.assertEqual((doc.problem_count, doc.max_severity), (1, "High"))
		self.assertEqual((doc.ndvi_latest, doc.ndvi_status), (0.52, "Stress detected"))
		self.assertAlmostEqual(doc.ndvi_change, -0.1)
		# 2 drippers × 403 plants × 4 L/h × 2 h = 6448 L, 16 L per plant (< 18): below requirement
		self.assertEqual((doc.irr_water_l, doc.irr_water_per_plant), (6448, 16))
		self.assertEqual(doc.irr_status, "Below requirement")

	def test_manual_plant_count_is_kept(self):
		doc = _consultation(self.customer)
		doc.crop_blocks[0].plants_manual = 1
		doc.crop_blocks[0].plant_count = 390
		doc.insert()
		self.assertEqual(doc.crop_blocks[0].plant_count, 390)

	def test_advisory_cards(self):
		doc = _consultation(self.customer, report_language="English", rain_probability=60, water_ec=2.5)
		doc.insert()
		titles = " | ".join(c["title"] for c in cc.advisory_cards(doc))
		for part in (
			"Spray / field-operation decision",
			"Crop health (NDVI)",
			"Water quality",
			"1. Case",
			"Irrigation check",
		):
			self.assertIn(part, titles)
		case = next(c for c in cc.advisory_cards(doc) if c["title"].startswith("1. Case"))
		self.assertIn("Fruit cracking", " ".join(case["items"]))  # "cracking" in the observation
		self.assertEqual(case["level"], "bad")
		mr = cc.advisory_cards(doc, "mr")
		self.assertIn("प्रकरण", mr[3]["title"])
		html = cc.advisory_html(doc)
		self.assertNotIn("<script", html)

	def test_user_text_is_escaped(self):
		doc = _consultation(self.customer)
		doc.problems[0].observation = "<img src=x onerror=alert(1)>"
		doc.insert()
		self.assertNotIn("<img src=x", cc.advisory_html(doc))
		html = frappe.get_print(CC, doc.name, "Crop Consultation Report", doc=doc)
		self.assertNotIn("<img src=x", html)

	def test_validation(self):
		doc = _consultation(self.customer, status="Agronomist Approved")
		self.assertRaises(frappe.ValidationError, doc.insert)
		doc.agronomist = "Dr. A. Kulkarni"
		doc.insert()
		self.assertRaises(frappe.ValidationError, _consultation(self.customer, latitude=95).insert)
		bad = _consultation(self.customer)
		bad.problems[0].block_no = 5
		self.assertRaises(frappe.ValidationError, bad.insert)
		bad = _consultation(self.customer)
		bad.ndvi_readings[0].ndvi = 1.5
		self.assertRaises(frappe.ValidationError, bad.insert)
		bad = _consultation(self.customer)
		bad.crop_blocks[0].variety = frappe.db.get_value("Farm Crop Variety", {"crop": "Mango"})
		if bad.crop_blocks[0].variety:
			self.assertRaises(frappe.ValidationError, bad.insert)

	def test_data_checks(self):
		doc = _consultation(self.customer, non_irrigated_area=2)
		doc.insert()
		checks = cc.area_checks(doc)
		self.assertFalse(checks[0][0])  # 5 ≠ 4 + 2
		self.assertTrue(all(ok for ok, *_ in checks[1:]))
		doc = _consultation(self.customer, total_area=1, irrigated_area=1, non_irrigated_area=0)
		doc.insert()
		self.assertFalse(next(ok for ok, en, _ in cc.area_checks(doc) if en.startswith("Crop-block")))

	def test_preview_matches_save(self):
		doc = _consultation(self.customer)
		payload = json.dumps({**doc.as_dict(convert_dates_to_str=True), "__islocal": 1}, default=str)
		out = api.preview_crop_consultation(payload)
		doc.insert()
		for f in ("crop_area_total", "total_plants", "ndvi_status", "irr_water_l", "max_severity"):
			self.assertEqual(out["parent"][f], doc.get(f), f)
		self.assertIn("fa-cc-card", out["panels"]["advisory_html"])
		self.assertIn("polyline", out["panels"]["ndvi_chart"])

	def test_print_whatsapp_report(self):
		doc = _consultation(self.customer, agronomist="Dr. A. Kulkarni", status="Issued to Farmer").insert()
		html = frappe.get_print(CC, doc.name, "Crop Consultation Report", doc=doc)
		self.assertIn("Pomegranate", html)
		self.assertIn("Boron", html)
		self.assertNotIn("DRAFT", html)
		msg = api.get_whatsapp_message(CC, doc.name)
		self.assertEqual(msg["number"], "91" + MOBILE)
		self.assertIn("Boron", msg["text"])
		from frappe.desk.query_report import run

		rows = run("Crop Consultation Register", filters={"customer": self.customer})["result"]
		self.assertIn(doc.name, [r["name"] for r in rows if isinstance(r, dict)])
		rows = run("Crop Consultation Register", filters={"crop": "Mango", "status": "Issued to Farmer"})[
			"result"
		]
		self.assertIn(doc.name, [r["name"] for r in rows if isinstance(r, dict)])

	def test_satyukt_endpoint(self):
		out = api.parse_satyukt_json('{"pest": "High", "ndvi": [{"date": "2026-08-01", "v": 0.6}]}')
		self.assertEqual(out["values"]["pest_risk"], "High")
		self.assertRaises(frappe.ValidationError, api.parse_satyukt_json, "{not json")

	def test_advisor_can_use_it(self):
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
			doc = _consultation(self.customer).insert()
			self.assertTrue(frappe.has_permission(CC, "print", doc))
			self.assertFalse(frappe.has_permission(CC, "delete", doc))
			self.assertTrue(frappe.has_permission("Address", "read"))
		finally:
			frappe.set_user("Administrator")


class TestAddressFetch(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.customer = _customer()
		for name in frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": "Customer", "link_name": self.customer, "parenttype": "Address"},
			pluck="parent",
		):
			frappe.delete_doc("Address", name, force=True, ignore_permissions=True)

	def test_no_address_falls_back_to_masters(self):
		d = get_farmer_details(self.customer)
		self.assertEqual((d["customer_address"], d["address_count"]), ("", 0))
		self.assertIn("Loni", d["address_display"])

	def test_primary_address_wins(self):
		_address(self.customer, "Field House")
		home = _address(self.customer, "Home", primary=1, city="Sangamner")
		d = get_farmer_details(self.customer)
		self.assertEqual((d["customer_address"], d["address_count"]), (home.name, 2))
		self.assertIn("Home, Gat No. 12", d["address_display"])
		self.assertIn("Sangamner", d["address_display"])
		# the dropdown offers only this farmer's addresses, primary first
		rows = customer_address_query("Address", "", "name", 0, 20, {"customer": self.customer})
		self.assertEqual(rows[0][0], home.name)
		self.assertEqual(len(rows), 2)

	def test_every_calculator_takes_and_checks_the_address(self):
		home = _address(self.customer, "Home", primary=1)
		other = _address(_customer_b(), "Elsewhere", primary=1)
		self.assertIn("Home", get_address_display(self.customer, home.name))
		self.assertRaises(frappe.ValidationError, get_address_display, self.customer, other.name)
		for make in (_spray, _basal, _consultation):
			doc = make(self.customer)
			doc.customer_address = home.name
			doc.address_display = ""
			doc.insert()
			self.assertIn("Home, Gat No. 12", doc.address_display, doc.doctype)
			# the text stays editable: a typed address is kept
			doc.address_display = "Near the temple, Loni"
			doc.save()
			self.assertEqual(doc.address_display, "Near the temple, Loni")
			bad = make(self.customer)
			bad.customer_address = other.name
			self.assertRaises(frappe.ValidationError, bad.insert)

	def test_address_used_on_print_when_no_masters(self):
		doc = _consultation(self.customer, village=None, taluka=None, district=None, state=None)
		doc.address_display = "Plot 4, Wadi Road\nLoni"
		doc.insert()
		self.assertEqual(doc.address_line("en"), "Plot 4, Wadi Road, Loni")


def _customer_b():
	from farm_advisory.utils.farmer import create_customer

	return create_customer(first_name="Sunil", last_name="Jadhav", mobile_no="9876500077")["customer"]
