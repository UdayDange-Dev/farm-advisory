"""Crop Consultation engine — the Agrismart Crop Consultancy prototype, server side.

Everything the prototype computed in the browser (area checks, plant counts,
NDVI trend, spray decision, soil / water alerts, irrigation calculator,
diagnosis knowledge base, follow-up plan) is computed here, so the saved
record, the form preview and the printed report always agree.

Chemicals are never chosen here: the engine lists possible causes and checks;
products and doses are entered by the agronomist in the Prescription table.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, escape_html, flt, getdate, today

from farm_advisory.utils import measure
from farm_advisory.utils.i18n import lang_key, tr
from farm_advisory.utils.numbers import fmt
from farm_advisory.utils.spray_calc import age

# tolerance for "equal" areas, in the farm's area unit (prototype: 0.01)
AREA_TOLERANCE = 0.01
FOLLOWUP_DAYS = (3, 7, 15, 30)
SEVERITY_ORDER = ("Low", "Medium", "High", "Critical")

# --- stored value -> Marathi (from the prototype's LISTS) ------------------ #
STAGES = {
	"Nursery": "रोपवाटिका",
	"Vegetative": "वाढीची अवस्था",
	"Flowering": "फुलोरा",
	"Fruit set": "फळधारणा",
	"Fruit development": "फळ वाढ",
	"Maturity": "परिपक्वता",
	"Harvest": "काढणी",
	"Post-harvest": "काढणीपश्चात",
	"Dormancy": "सुप्तावस्था",
	"Other": "इतर",
}
PROBLEMS = {
	"Insect / Pest": "कीड",
	"Disease": "रोग",
	"Nutrient deficiency": "अन्नद्रव्य कमतरता",
	"Weed": "तण",
	"Water stress": "पाण्याचा ताण",
	"Salinity": "क्षारता",
	"Physiological disorder": "शारीरिक विकृती",
	"Unknown / Other": "अज्ञात / इतर",
}
PARTS = {
	"Leaf": "पान",
	"Stem": "खोड",
	"Root": "मूळ",
	"Flower": "फूल",
	"Fruit": "फळ",
	"Whole plant": "संपूर्ण झाड",
	"Soil zone": "जमीन / मुळांचा भाग",
}
SEVERITY = {"Low": "कमी", "Medium": "मध्यम", "High": "जास्त", "Critical": "गंभीर"}
PEST_RISK = {"Low": "कमी", "Moderate": "मध्यम", "High": "जास्त", "Very High": "अतिजास्त"}
METHODS = {
	"Spray": "फवारणी",
	"Drip / Fertigation": "ठिबक / फर्टिगेशन",
	"Soil application": "जमिनीतून",
	"Drenching": "आळवणी",
	"Other": "इतर",
}
STATUS = {"Draft": "मसुदा", "Agronomist Approved": "तज्ज्ञ मान्य", "Issued to Farmer": "शेतकऱ्यास दिले"}
LEVELS = ("Low", "Medium", "High")

# --- diagnosis knowledge base: c = possible causes, a = checks / actions --- #
KB = {
	"Insect / Pest": {
		"c": [
			("Pest build-up favoured by weather or crop stage", "हवामान किंवा पीक अवस्थेमुळे किडीची वाढ"),
			("Nearby infested plots", "शेजारील प्लॉटमधील प्रादुर्भाव"),
			("Excess nitrogen / soft growth", "जास्त नत्र / मऊ वाढ"),
		],
		"a": [
			(
				"Identify the pest (photo, hand lens); count per plant/leaf against threshold",
				"किडीची ओळख (फोटो, भिंग); प्रति झाड/पान संख्या मोजा",
			),
			(
				"Prefer cultural / bio-control first; chemical only if threshold crossed, as agronomist advises",
				"आधी मशागतीय / जैविक उपाय; मर्यादा ओलांडल्यास तज्ज्ञ सांगतील तेच रसायन",
			),
			(
				"Rotate modes of action; observe pre-harvest interval",
				"कार्यपद्धती बदलत्या ठेवा; काढणीपूर्व कालावधी पाळा",
			),
		],
	},
	"Disease": {
		"c": [
			("High humidity / rain / leaf wetness", "जास्त आर्द्रता / पाऊस / पाने ओली राहणे"),
			("Poor drainage or dense canopy", "निचरा कमी किंवा दाट छत्र"),
			("Infected planting material or previous infection", "संक्रमित लागवड साहित्य किंवा आधीचा रोग"),
		],
		"a": [
			(
				"Confirm disease: fungal / bacterial / viral — send sample to lab if unsure",
				"रोग निश्चित करा: बुरशी / जिवाणू / विषाणू — शंका असल्यास प्रयोगशाळेत नमुना द्या",
			),
			(
				"Remove and destroy infected parts; improve air flow and drainage",
				"बाधित भाग काढून नष्ट करा; हवा खेळती व निचरा सुधारा",
			),
			(
				"Protectant / curative selection by agronomist only after confirmation",
				"निश्चितीनंतरच तज्ज्ञाकडून संरक्षक / उपचारात्मक निवड",
			),
		],
	},
	"Nutrient deficiency": {
		"c": [
			("Low availability in soil / pH or EC imbalance", "जमिनीत कमी उपलब्धता / pH किंवा EC असंतुलन"),
			(
				"Poor root activity (waterlogging, nematodes, compaction)",
				"मुळांची कमकुवत क्रिया (पाणी साचणे, निमॅटोड, घट्ट जमीन)",
			),
			("Fertigation / fertilizer schedule gap", "फर्टिगेशन / खत वेळापत्रकात खंड"),
		],
		"a": [
			(
				"Check pattern: old vs new leaves, uniform vs patchy",
				"पॅटर्न तपासा: जुनी की नवीन पाने, एकसारखे की ठिपक्यांचे",
			),
			(
				"Take soil and petiole/leaf sample; compare with Satyukt soil layer",
				"माती व देठ/पान नमुना घ्या; Satyukt मृदा माहितीशी तुलना करा",
			),
			(
				"Correct via fertigation / foliar after test; recheck in 7–10 days",
				"चाचणीनंतर फर्टिगेशन / फवारणीने सुधारणा; ७–१० दिवसांनी पुन्हा तपासा",
			),
		],
	},
	"Weed": {
		"c": [("Seed bank, late weeding, open canopy", "तणांचे बी, उशिरा खुरपणी, मोकळे छत्र")],
		"a": [
			("Identify weed type (grass / broadleaf / sedge)", "तणाचा प्रकार ओळखा (गवत / रुंद पान / लव्हाळा)"),
			(
				"Mulch / inter-cultivation first; herbicide only as per label and crop safety",
				"आधी आच्छादन / आंतरमशागत; तणनाशक लेबल व पीक सुरक्षेनुसारच",
			),
		],
	},
	"Water stress": {
		"c": [
			("Insufficient or irregular irrigation", "अपुरे किंवा अनियमित सिंचन"),
			("Clogged emitters / low pressure / poor uniformity", "ड्रिपर चोकअप / कमी दाब / असमान वितरण"),
			("High ET / heat / wind", "जास्त बाष्पोत्सर्जन / उष्णता / वारा"),
		],
		"a": [
			(
				"Audit drip: pressure, discharge per dripper, filter condition",
				"ठिबक तपासणी: दाब, ड्रिपर विसर्ग, फिल्टर स्थिती",
			),
			(
				"Check root-zone moisture before changing schedule",
				"वेळापत्रक बदलण्यापूर्वी मुळांच्या भागातील ओलावा तपासा",
			),
			(
				"Use the irrigation calculator to compare applied vs required water",
				"सिंचन कॅल्क्युलेटरने दिलेले व आवश्यक पाणी तुलना करा",
			),
		],
	},
	"Salinity": {
		"c": [
			(
				"High EC / sodium / bicarbonate in water or soil",
				"पाणी किंवा जमिनीत जास्त EC / सोडियम / बायकार्बोनेट",
			)
		],
		"a": [
			("Test water and soil EC, pH, Na, HCO₃", "पाणी व माती EC, pH, Na, HCO₃ तपासा"),
			(
				"Plan leaching, gypsum/acid treatment and fertilizer choice on lab advice",
				"प्रयोगशाळा सल्ल्यानुसार निचरा, जिप्सम/ॲसिड उपचार व खत निवड",
			),
		],
	},
	"Physiological disorder": {
		"c": [
			("Irregular moisture swings", "ओलाव्यातील अनियमित चढउतार"),
			("Calcium / boron imbalance", "कॅल्शियम / बोरॉन असंतुलन"),
			("Temperature extremes, variety susceptibility", "तापमान टोकाचे, वाणाची संवेदनशीलता"),
		],
		"a": [
			("Stabilise irrigation; avoid sudden heavy watering", "सिंचन स्थिर ठेवा; अचानक जास्त पाणी टाळा"),
			(
				"Review nutrition (Ca, B, K) with soil/leaf analysis",
				"माती/पान विश्लेषणासह पोषण (Ca, B, K) तपासा",
			),
			("Record affected % weekly to track trend", "कल पाहण्यासाठी बाधित % दर आठवड्याला नोंदवा"),
		],
	},
	"Unknown / Other": {
		"c": [("Cause not yet clear", "कारण अजून स्पष्ट नाही")],
		"a": [
			(
				"Collect more photos, samples and history; refer to senior agronomist / KVK",
				"अधिक फोटो, नमुने व इतिहास गोळा करा; वरिष्ठ तज्ज्ञ / KVK कडे पाठवा",
			)
		],
	},
}
CRACKING = (
	"Fruit cracking: stabilise irrigation, check emitter uniformity and Ca/B/K status; "
	"avoid sudden heavy irrigation after dry spell.",
	"फळांना तडे: सिंचन स्थिर ठेवा, ड्रिपर एकसमानता व Ca/B/K तपासा; कोरड्या कालावधीनंतर अचानक जास्त पाणी टाळा.",
)
CRACK_WORDS = ("crack", "तडे", "तडा", "फुट")


# --------------------------------------------------------------------------- #
# Pure calculations
# --------------------------------------------------------------------------- #
def block_calc(b, visit_date):
	"""Plant age, area in acres and (unless typed in) the plant count of one crop block."""
	b.area_unit = b.area_unit or "Acre"
	b.spacing_unit = b.spacing_unit or "Feet"
	b.area_acre = measure.convert_area(b.area, b.area_unit, "Acre")
	b.plant_age = age(b.plantation_date, visit_date, "en")[0] if b.get("plantation_date") else ""
	if not cint(b.plants_manual):
		b.plant_count = measure.plant_count(
			b.area, b.area_unit, b.row_spacing, b.plant_spacing, b.spacing_unit
		)


def ndvi_status(readings):
	"""Trend of the two latest readings: ``(latest, change, status)``.

	A reading of 0 or less is treated as "not entered" (a Float field cannot
	be blank, and NDVI ≤ 0 is water / bare soil, not a crop canopy). The change
	is rounded to 6 places before comparing, so 0.52 → 0.62 counts as the
	-0.10 drop it is, not -0.0999999.
	"""
	pts = sorted(
		(
			(getdate(r.reading_date), flt(r.ndvi))
			for r in readings or []
			if r.reading_date and flt(r.ndvi) > 0
		),
		key=lambda x: x[0],
	)
	if not pts:
		return None, None, ""
	latest = pts[-1][1]
	if len(pts) < 2:
		return latest, None, ""
	d = round(latest - pts[-2][1], 6)
	status = "Stress detected" if d <= -0.10 else "Moderate stress" if d <= -0.03 else "Healthy / stable"
	return latest, d, status


def spray_decision(rain, wind, humidity, temperature):
	"""``sprayDecision()``: ``(decision, reasons)``; ("", []) when no weather is entered."""
	if not any(flt(x) for x in (rain, wind, humidity, temperature)):
		return "", []
	why, level = [], "ok"
	if flt(rain) >= 40:
		why.append(("Rain probability high", "पावसाची शक्यता जास्त"))
		level = "bad"
	if flt(wind) > 15:
		why.append(("Wind too strong (drift)", "वारा जास्त (फवारा वाहून जाईल)"))
		level = "bad"
	if flt(humidity) >= 85:
		why.append(("High humidity — disease pressure rising", "आर्द्रता जास्त — रोगाचा धोका वाढतो"))
		level = "warn" if level == "ok" else level
	if flt(temperature) >= 35:
		why.append(("High temperature — spray early morning only", "तापमान जास्त — फक्त सकाळी लवकर फवारणी"))
		level = "warn" if level == "ok" else level
	return {"ok": "Suitable", "warn": "Spray with caution", "bad": "Do not spray"}[level], why


def irrigation(block, dripper_lph, drippers_per_plant, total_drippers, hours, required_per_plant):
	"""``irrCalc()`` for one crop block. Unrounded; the depth uses the exact m² of the block.

	1 litre spread over 1 m² is 1 mm, so depth (mm) = litres ÷ area (m²).
	"""
	plants = flt(block.plant_count) if block else 0
	n = flt(drippers_per_plant) * plants or flt(total_drippers)
	flow = n * flt(dripper_lph)
	litres = flow * flt(hours)
	per_plant = litres / plants if plants else 0
	area_m2 = measure.to_sq_m(block.area, block.area_unit) if block else 0
	depth = litres / area_m2 if area_m2 else 0
	req = flt(required_per_plant)
	status = ""
	if req and per_plant:
		status = (
			"Below requirement"
			if per_plant < req * 0.9
			else "Above requirement"
			if per_plant > req * 1.1
			else "Close to requirement"
		)
	return {
		"drippers": n,
		"flow": flow,
		"litres": litres,
		"per_plant": per_plant,
		"depth": depth,
		"status": status,
	}


def area_checks(doc):
	"""The prototype's live checks / ``validate()`` list: ``[(ok, en, mr)]`` (all areas in acres)."""
	u = doc.farm_area_unit or "Acre"

	def ac(v):
		return measure.convert_area(v, u, "Acre")

	tot, irr, non = flt(doc.total_area), flt(doc.irrigated_area), flt(doc.non_irrigated_area)
	tol = AREA_TOLERANCE
	out = []
	if not (doc.first_name and doc.last_name and doc.mobile_no):
		out.append(
			(False, "Farmer first name, last name and mobile required", "शेतकऱ्याचे नाव, आडनाव व मोबाईल आवश्यक")
		)
	if not (flt(doc.latitude) or flt(doc.longitude)):
		out.append((False, "GPS location not captured", "GPS ठिकाण नोंदवले नाही"))
	if tot or irr or non:
		ok = tot > 0 and abs(tot - irr - non) < tol
		out.append(
			(
				ok,
				f"Total {fmt(tot)} {'=' if ok else '≠'} Irrigated {fmt(irr)} + Non-irrigated {fmt(non)} ({u})",
				f"एकूण {fmt(tot)} {'=' if ok else '≠'} सिंचित {fmt(irr)} + कोरडवाहू {fmt(non)} ({u})",
			)
		)
	crop = flt(doc.crop_area_total)
	if crop:
		ok = not tot or crop <= ac(tot) + measure.convert_area(tol, u, "Acre")
		out.append(
			(
				ok,
				f"Crop-block area {fmt(crop, 4)} acre / farm total {fmt(ac(tot), 4)} acre",
				f"पीक विभाग क्षेत्र {fmt(crop, 4)} एकर / शेत एकूण {fmt(ac(tot), 4)} एकर",
			)
		)
	holders = flt(doc.landholder_area_total)
	if doc.get("landholders") and flt(doc.family_area):
		ok = abs(ac(doc.family_area) - holders) < measure.convert_area(tol, u, "Acre")
		out.append(
			(
				ok,
				f"Landholders total {fmt(holders, 4)} acre vs family area {fmt(ac(doc.family_area), 4)} acre",
				f"जमीनधारक एकूण {fmt(holders, 4)} एकर विरुद्ध कुटुंब क्षेत्र {fmt(ac(doc.family_area), 4)} एकर",
			)
		)
	if not doc.get("problems") and not doc.get("photos"):
		out.append((False, "No diagnosis case or photo recorded", "निदान किंवा फोटो नाही"))
	return out


def followup_dates(visit_date):
	if not visit_date:
		return []
	return [(d, add_days(getdate(visit_date), d)) for d in FOLLOWUP_DAYS]


def irr_block(doc):
	blocks = doc.get("crop_blocks") or []
	n = cint(doc.irr_block_no) or 1
	return next((b for b in blocks if cint(b.block_no) == n), blocks[0] if blocks else None)


# --------------------------------------------------------------------------- #
# Document
# --------------------------------------------------------------------------- #
def apply_consultation_calculation(doc):
	for i, b in enumerate(doc.get("crop_blocks") or [], start=1):
		b.block_no = i
		block_calc(b, doc.visit_date)
	blocks = doc.get("crop_blocks") or []
	doc.crop_area_total = sum(flt(b.area_acre) for b in blocks)
	doc.total_plants = sum(cint(b.plant_count) for b in blocks)
	doc.crop_summary = ", ".join(dict.fromkeys(b.crop for b in blocks if b.crop))
	doc.landholder_area_total = sum(flt(h.area) for h in doc.get("landholders") or [])

	problems = doc.get("problems") or []
	doc.problem_count = len(problems)
	sev = [SEVERITY_ORDER.index(p.severity) for p in problems if p.severity in SEVERITY_ORDER]
	doc.max_severity = SEVERITY_ORDER[max(sev)] if sev else ""

	doc.ndvi_latest, doc.ndvi_change, doc.ndvi_status = ndvi_status(doc.get("ndvi_readings"))
	doc.ndvi_latest, doc.ndvi_change = flt(doc.ndvi_latest), flt(doc.ndvi_change)
	doc.spray_decision = spray_decision(doc.rain_probability, doc.wind_speed, doc.humidity, doc.temperature)[
		0
	]

	ic = irrigation(
		irr_block(doc),
		doc.dripper_lph,
		doc.irr_drippers_per_plant,
		doc.irr_total_drippers,
		doc.irr_hours,
		doc.irr_required_per_plant,
	)
	doc.irr_dripper_count = ic["drippers"]
	doc.irr_flow_lph = ic["flow"]
	doc.irr_water_l = ic["litres"]
	doc.irr_water_per_plant = ic["per_plant"]
	doc.irr_depth_mm = ic["depth"]
	doc.irr_status = ic["status"]


# --------------------------------------------------------------------------- #
# Advisory (HTML for the form; cards for the print format)
# --------------------------------------------------------------------------- #
def _crop_label(doc, crop, lang):
	if not crop:
		return ""
	return tr(crop, frappe.db.get_value("Farm Crop", crop, "crop_name_mr"), lang)


def advisory_cards(doc, lang=None):
	"""``engineHTML()`` as data: ``[{level, title, items, five}]`` (level ok / warn / bad)."""
	lang = lang or lang_key(doc.report_language)

	def t(en, mr=None):
		return tr(en, mr, lang)

	def lines(pairs):
		return [t(en, mr) for en, mr in pairs]

	cards = []
	decision, why = spray_decision(doc.rain_probability, doc.wind_speed, doc.humidity, doc.temperature)
	if decision:
		level = {"Suitable": "ok", "Spray with caution": "warn", "Do not spray": "bad"}[decision]
		if level == "bad":
			items = [("Do not spray now.", "आत्ता फवारणी करू नका."), *why]
			items.append(
				(
					"Re-check forecast; next window usually early morning (about 6:30–9:00) when wind is calm and no rain is forecast.",
					"अंदाज पुन्हा तपासा; वारा शांत व पाऊस नसताना सकाळी (साधारण ६:३०–९:००) फवारणी योग्य.",
				)
			)
		elif level == "warn":
			items = [("Spray with caution.", "काळजीपूर्वक फवारणी करा."), *why]
		else:
			items = [("Conditions suitable; prefer 6:30–9:00 AM.", "परिस्थिती योग्य; सकाळी ६:३०–९:०० योग्य.")]
		cards.append(
			{
				"level": level,
				"title": "🌦️ " + t("Spray / field-operation decision", "फवारणी / शेतकाम निर्णय"),
				"items": lines(items),
			}
		)

	latest, change, status = ndvi_status(doc.get("ndvi_readings"))
	if status:
		level = {"Stress detected": "bad", "Moderate stress": "warn"}.get(status, "ok")
		label = {
			"Stress detected": ("🔴 Stress detected", "🔴 ताण आढळला"),
			"Moderate stress": ("🟡 Moderate stress", "🟡 मध्यम ताण"),
		}.get(status, ("🟢 Healthy / stable", "🟢 निरोगी / स्थिर"))
		sign = "+" if change >= 0 else ""
		items = [
			(
				f"Latest NDVI {latest:.2f}, change {sign}{change:.2f} vs previous reading.",
				f"ताजा NDVI {latest:.2f}, मागील नोंदीपेक्षा बदल {sign}{change:.2f}.",
			)
		]
		if level != "ok":
			items.append(
				(
					"Physically inspect the yellow/red zone: roots, irrigation uniformity, pest/disease.",
					"पिवळ्या/लाल भागाची प्रत्यक्ष पाहणी: मुळे, सिंचन एकसमानता, कीड/रोग.",
				)
			)
		cards.append(
			{
				"level": level,
				"title": "🛰️ " + t("Crop health (NDVI)", "पीक आरोग्य (NDVI)") + ": " + t(*label),
				"items": lines(items),
			}
		)

	soil = []
	for field, en, mr in (
		("soil_n", "Nitrogen", "नत्र"),
		("soil_p", "Phosphorus", "स्फुरद"),
		("soil_k", "Potassium", "पालाश"),
		("soil_organic_carbon", "Organic carbon", "सेंद्रिय कर्ब"),
	):
		v = doc.get(field)
		if v == "Low":
			soil.append(
				(
					f"{en} estimated LOW — confirm by soil test, then adjust programme for crop stage and yield target.",
					f"{mr} अंदाजे कमी — माती चाचणीने खात्री करा, नंतर पीक अवस्था व उत्पादन लक्ष्यानुसार कार्यक्रम बदला.",
				)
			)
		elif v == "High" and field != "soil_organic_carbon":
			soil.append(
				(
					f"{en} estimated HIGH — avoid unnecessary additions.",
					f"{mr} अंदाजे जास्त — अनावश्यक वापर टाळा.",
				)
			)
	ph = flt(doc.soil_ph)
	if ph >= 8:
		soil.append(
			(
				"pH ≥ 8: check availability of Fe, Zn, Mn, P; consider acidification/water treatment on lab advice.",
				"pH ≥ ८: Fe, Zn, Mn, P ची उपलब्धता तपासा; प्रयोगशाळा सल्ल्यानुसार आम्लीकरण/पाणी उपचार विचारात घ्या.",
			)
		)
	elif 0 < ph < 5.5:
		soil.append(
			(
				"pH < 5.5: acidity — liming decision on lab advice.",
				"pH < ५.५: आम्लता — चुना वापर प्रयोगशाळा सल्ल्यानुसार.",
			)
		)
	if soil:
		cards.append(
			{
				"level": "warn",
				"title": "🧪 " + t("Soil intelligence (satellite estimate)", "मृदा माहिती (उपग्रह अंदाज)"),
				"items": lines(soil),
			}
		)

	water = []
	if flt(doc.water_ec) >= 2:
		water.append(
			(
				"Water EC ≥ 2 dS/m: salinity risk; watch crop tolerance and leaching.",
				"पाणी EC ≥ २ dS/m: क्षारतेचा धोका; पिकाची सहनशीलता व निचरा पहा.",
			)
		)
	if flt(doc.water_bicarbonate) >= 300:
		water.append(
			(
				"High bicarbonate: emitter clogging and iron/zinc lock-up risk; consider acid treatment.",
				"जास्त बायकार्बोनेट: ड्रिपर चोकअप व लोह/जस्त अडकण्याचा धोका; ॲसिड उपचार विचारा.",
			)
		)
	if water:
		cards.append(
			{
				"level": "warn",
				"title": "💧 " + t("Water quality alerts", "पाणी गुणवत्ता सूचना"),
				"items": lines(water),
			}
		)

	if doc.pest_risk in ("High", "Very High"):
		cards.append(
			{
				"level": "bad",
				"title": "🐛 "
				+ t("Pest/disease forewarning: ", "कीड/रोग पूर्वसूचना: ")
				+ t(doc.pest_risk, PEST_RISK.get(doc.pest_risk)),
				"items": lines(
					[
						(
							"Scout the field within 24–48 h and record counts before any treatment.",
							"कोणत्याही उपचारापूर्वी २४–४८ तासांत पाहणी करून संख्या नोंदवा.",
						)
					]
				),
			}
		)

	for i, p in enumerate(doc.get("problems") or [], start=1):
		k = KB.get(p.problem_type)
		if not k:
			continue
		actions = list(k["a"])
		obs = (p.observation or "").lower()
		if any(w in obs for w in CRACK_WORDS):
			actions.insert(0, CRACKING)
		level = "bad" if p.severity in ("Critical", "High") else "warn" if p.severity == "Medium" else "ok"
		bits = [t(p.problem_type, PROBLEMS.get(p.problem_type))]
		if p.affected_part:
			bits.append(t(p.affected_part, PARTS.get(p.affected_part)))
		if p.severity:
			bits.append(t(p.severity, SEVERITY.get(p.severity)))
		if flt(p.affected_pct):
			bits.append(f"{fmt(p.affected_pct)}%")
		block = f" · {t('Block', 'विभाग')} {p.block_no}" if cint(p.block_no) else ""
		when = (
			("Within 24–48 hours", "२४–४८ तासांत")
			if level == "bad"
			else ("Within the week; follow-up in 7 days", "आठवड्याच्या आत; ७ दिवसांनी पाठपुरावा")
		)
		cards.append(
			{
				"level": level,
				"title": f"{i}. {t('Case', 'प्रकरण')}: " + " · ".join(bits) + block,
				"items": [t("Possible causes:", "संभाव्य कारणे:")]
				+ ["• " + x for x in lines(k["c"])]
				+ [t("Checks / actions:", "तपासण्या / उपाय:")]
				+ ["• " + x for x in lines(actions)],
				"five": [
					(
						t("WHAT", "काय"),
						t("Confirm cause, then act on the items below", "कारण निश्चित करा, मग खालील उपाय करा"),
					),
					(
						t("WHY", "का"),
						t(
							"Matches the recorded evidence; to be validated by agronomist",
							"नोंदवलेल्या पुराव्याशी जुळते; तज्ज्ञ पडताळणी आवश्यक",
						),
					),
					(
						t("HOW", "कसे"),
						t(
							"As per checks above; products & method set by agronomist",
							"वरील तपासण्यांनुसार; उत्पादन व पद्धत तज्ज्ञ ठरवतात",
						),
					),
					(t("WHEN", "केव्हा"), t(*when)),
					(
						t("HOW MUCH", "किती"),
						t(
							"Dose / volume per label and agronomist (record in Prescription)",
							"मात्रा / पाणी लेबल व तज्ज्ञानुसार (शिफारसीत नोंदवा)",
						),
					),
				],
			}
		)

	if doc.irr_status:
		level = {"Below requirement": "bad", "Above requirement": "warn"}.get(doc.irr_status, "ok")
		msg = {
			"Below requirement": (
				"Applied water is below requirement — increase duration/frequency after checking root-zone moisture.",
				"दिलेले पाणी आवश्यकतेपेक्षा कमी — ओलावा तपासून कालावधी/वारंवारता वाढवा.",
			),
			"Above requirement": (
				"Applied water exceeds requirement — risk of waste/leaching; reduce after moisture check.",
				"दिलेले पाणी आवश्यकतेपेक्षा जास्त — अपव्यय/निचरा धोका; ओलावा पाहून कमी करा.",
			),
		}.get(doc.irr_status, ("Applied water is close to requirement.", "दिलेले पाणी आवश्यकतेच्या जवळ आहे."))
		cards.append(
			{"level": level, "title": "💧 " + t("Irrigation check", "सिंचन तपासणी"), "items": lines([msg])}
		)
	return cards


def advisory_html(doc):
	"""The form's Advisory, Data Checks and Follow-up panels (escaped; no user HTML passes through)."""
	lang = lang_key(doc.report_language)

	def t(en, mr=None):
		return tr(en, mr, lang)

	e = escape_html
	chips = []
	for b in doc.get("crop_blocks") or []:
		bits = [
			_crop_label(doc, b.crop, lang),
			b.variety or "",
			t(b.crop_stage, STAGES.get(b.crop_stage)) if b.crop_stage else "",
		]
		bits.append(f"{fmt(b.area_acre, 2)} {t('acre', 'एकर')}" if flt(b.area_acre) else "")
		chips.append(f'<span class="fa-cc-chip">{b.block_no}. {e(" · ".join(x for x in bits if x))}</span>')
	parts = [
		f'<div class="fa-cc">{"".join(chips)}'
		f'<div class="fa-cc-note warn">{e(t("Recommendation = Crop + Variety + Age + Stage + Problem + Weather + Satellite evidence. Chemicals are never auto-selected.", "शिफारस = पीक + वाण + वय + अवस्था + समस्या + हवामान + उपग्रह पुरावा. रसायने आपोआप निवडली जात नाहीत."))}</div>'
	]
	cards = advisory_cards(doc, lang)
	if not cards:
		parts.append(
			f'<div class="fa-cc-note">{e(t("Enter weather, satellite, water-quality or diagnosis details to see advice.", "सल्ला पाहण्यासाठी हवामान, उपग्रह, पाणी गुणवत्ता किंवा निदान माहिती भरा."))}</div>'
		)
	for c in cards:
		five = ""
		if c.get("five"):
			five = (
				'<div class="fa-cc-w5">'
				+ "".join(f"<b>{e(k)}</b><span>{e(v)}</span>" for k, v in c["five"])
				+ "</div>"
			)
		items = "".join(f"<li>{e(x)}</li>" for x in c["items"])
		parts.append(
			f'<div class="fa-cc-card {c["level"]}"><h4>{e(c["title"])}</h4>{five}<ul>{items}</ul></div>'
		)
	parts.append("</div>")
	return "".join(parts)


def checks_html(doc):
	lang = lang_key(doc.report_language)
	rows = area_checks(doc)
	if not rows:
		return ""
	return (
		'<div class="fa-cc">'
		+ "".join(
			f'<div class="fa-cc-note {"ok" if ok else "bad"}">{"✓" if ok else "⚠"} {escape_html(tr(en, mr, lang))}</div>'
			for ok, en, mr in rows
		)
		+ "</div>"
	)


def followup_html(doc):
	lang = lang_key(doc.report_language)
	return (
		'<div class="fa-cc">'
		+ "".join(
			f'<span class="fa-cc-chip">{escape_html(tr("Day", "दिवस", lang))} {d}: {dt.strftime("%d-%m-%Y")}</span>'
			for d, dt in followup_dates(doc.visit_date)
		)
		+ "</div>"
	)


def ndvi_svg(doc):
	"""The prototype's NDVI sparkline (values clamped to 0–1)."""
	pts = sorted(
		(
			(getdate(r.reading_date), flt(r.ndvi))
			for r in doc.get("ndvi_readings") or []
			if r.reading_date and flt(r.ndvi) > 0
		),
		key=lambda x: x[0],
	)
	if len(pts) < 2:
		return ""
	w, h = 300, 90

	def xs(i):
		return 10 + i * (w - 20) / (len(pts) - 1)

	def ys(v):
		return h - 10 - max(0, min(1, v)) * (h - 20)

	line = " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, (_, v) in enumerate(pts))
	dots = "".join(
		f'<circle cx="{xs(i):.1f}" cy="{ys(v):.1f}" r="3.5" fill="#174b3b"/>' for i, (_, v) in enumerate(pts)
	)
	return (
		f'<svg viewBox="0 0 {w} {h}" style="width:100%;max-width:420px;background:#f6fbf8;border-radius:10px">'
		f'<polyline fill="none" stroke="#2f8b68" stroke-width="2.5" points="{line}"/>{dots}</svg>'
	)


# --------------------------------------------------------------------------- #
# Satyukt JSON import
# --------------------------------------------------------------------------- #
def parse_satyukt(data):
	"""Field values from the prototype's Satyukt JSON paste.

	``{"ndvi":[{"date","v"|"ndvi","blk"}], "soil":{"n","p","k","soc","ph"},
	"moisture", "pest", "weather":{"rain","wind","hum","temp"}}``. Unknown keys
	are ignored; level values must be one of the field's options.
	"""
	if not isinstance(data, dict):
		frappe.throw(_("Invalid JSON: expected an object."))
	out, ndvi = {}, []
	for r in data.get("ndvi") or []:
		if not isinstance(r, dict) or not r.get("date"):
			continue
		v = r.get("v", r.get("ndvi"))
		try:
			getdate(r["date"])
		except Exception:
			frappe.throw(_("Invalid NDVI date: {0}").format(r["date"]))
		ndvi.append(
			{"reading_date": str(getdate(r["date"])), "ndvi": flt(v), "crop_block": str(r.get("blk") or "")}
		)
	soil = data.get("soil") or {}

	def level(v, allowed=LEVELS):
		return v if v in allowed else None

	for key, field in (("n", "soil_n"), ("p", "soil_p"), ("k", "soil_k"), ("soc", "soil_organic_carbon")):
		if level(soil.get(key)):
			out[field] = soil[key]
	if soil.get("ph") not in (None, ""):
		out["soil_ph"] = flt(soil["ph"])
	if level(data.get("moisture")):
		out["soil_moisture"] = data["moisture"]
	if level(data.get("pest"), tuple(PEST_RISK)):
		out["pest_risk"] = data["pest"]
	wx = data.get("weather") or {}
	for key, field in (
		("rain", "rain_probability"),
		("wind", "wind_speed"),
		("hum", "humidity"),
		("temp", "temperature"),
	):
		if wx.get(key) not in (None, ""):
			out[field] = flt(wx[key])
	out["satyukt_linked"] = 1
	out["satellite_data_date"] = today()
	return {"values": out, "ndvi": ndvi}
