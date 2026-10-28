"""Default master data, copied verbatim from the two reference calculators.

Spray values come from ``defaults()``/``BRANCHES``/``COMPANY`` in
``Spray_Schedule_Calculator.html``; basal values from ``VARIETIES``,
``SPACING``, ``FERT0``, ``TPL``, ``STATES`` and ``DIST`` in
``basal-dose-calculator.html`` (which in turn came from the Besal Dose Excel).
Do not "correct" figures here — change them in the masters after install.
"""

COMPANY_NAME = "AGRI SMART FARM SOLUTIONS LLP"
COMPANY_EMAIL = "agrismartfarmsolutionsllp@gmail.com"
REPORT_TAGLINE = "Agri Smart – a smart way of farming"

BRANCHES = [
	# (branch, Marathi name, address, phone)
	(
		"Head Office – Sangamner",
		"मुख्य कार्यालय – संगमनेर",
		"Murli Shankutal (Kesekar) Complex, North Block, First Floor\n"
		"Opp. Market Yard, Sangamner, Tal. Sangamner, Dist. Ahilyanagar (M.S.) – 422605",
		"9373945000, 9373947000",
	),
	(
		"Sangamner Branch",
		"संगमनेर शाखा",
		"957, Shop No. 8, Opp. Bharat Petroleum\n"
		"Sangamner, Tal. Sangamner, Dist. Ahilyanagar (M.S.) – 422605",
		"9850675999, 9373947000",
	),
	(
		"Loni Branch",
		"लोणी शाखा",
		"Loni–Babhaleshwar Road, At Loni Khurd\nTal. Rahata, Dist. Ahilyanagar (M.S.) – 413713",
		"9373942000, 9850966366",
	),
	(
		"Talegaon Branch",
		"तळेगाव शाखा",
		"Near Indian Oil Petroleum, Sangamner–Kopargaon Road, Talegaon\n"
		"Tal. Sangamner, Dist. Ahilyanagar (M.S.) – 422611",
		"8788872618, 9373947000",
	),
]

VILLAGES = [("Jawle Kadlag", "जवळे कडलग"), ("Loni", "लोणी"), ("Talegaon Dighe", "तळेगाव दिघे")]
TALUKAS = [("Sangamner", "संगमनेर"), ("Rahata", "राहाता"), ("Shrirampur", "श्रीरामपूर")]
# Spray list first (with Marathi), then the Basal list
DISTRICTS = [
	("Ahilyanagar", "अहिल्यानगर"),
	("Pune", "पुणे"),
	("Nashik", "नाशिक"),
	("Solapur", None),
	("Satara", None),
	("Sangli", None),
	("Kolhapur", None),
	("Ahmednagar", None),
	("Latur", None),
	("Dharashiv (Osmanabad)", None),
	("Beed", None),
	("Jalna", None),
	("Chhatrapati Sambhajinagar", None),
	("Nanded", None),
	("Dhule", None),
	("Jalgaon", None),
	("Buldhana", None),
	("Akola", None),
]
STATES = [
	("Maharashtra", "महाराष्ट्र"),
	("Gujarat", "गुजरात"),
	("Karnataka", "कर्नाटक"),
	("Madhya Pradesh", "मध्य प्रदेश"),
	("Goa", "गोवा"),
	("Rajasthan", "राजस्थान"),
	("Telangana", "तेलंगणा"),
	("Andhra Pradesh", "आंध्र प्रदेश"),
	("Tamil Nadu", "तमिळनाडू"),
	("Kerala", "केरळ"),
	("Chhattisgarh", "छत्तीसगड"),
	("Uttar Pradesh", "उत्तर प्रदेश"),
	("Bihar", "बिहार"),
	("West Bengal", "पश्चिम बंगाल"),
	("Odisha", "ओडिशा"),
	("Punjab", "पंजाब"),
	("Haryana", "हरियाणा"),
	("Himachal Pradesh", "हिमाचल प्रदेश"),
	("Uttarakhand", "उत्तराखंड"),
	("Jharkhand", "झारखंड"),
	("Assam", "आसाम"),
	("Delhi", "दिल्ली"),
	("Jammu & Kashmir", "जम्मू आणि काश्मीर"),
]

# crop -> (Marathi, used in spray, used in basal, row ft, plant ft)
# Guava / Mango / Papaya Marathi names are plain translations of the crop name;
# the basal prototype was English-only.
CROPS = {
	"Pomegranate": ("डाळिंब", 1, 1, 12, 9),
	"Grapes": ("द्राक्ष", 1, 0, 0, 0),
	"Onion": ("कांदा", 1, 0, 0, 0),
	"Sugarcane": ("ऊस", 1, 0, 0, 0),
	"Tomato": ("टोमॅटो", 1, 0, 0, 0),
	"Banana": ("केळी", 1, 1, 6, 5),
	"Soybean": ("सोयाबीन", 1, 0, 0, 0),
	"Cotton": ("कापूस", 1, 0, 0, 0),
	"Maize": ("मका", 1, 0, 0, 0),
	"Wheat": ("गहू", 1, 0, 0, 0),
	"Guava": ("पेरू", 0, 1, 12, 6),
	"Mango": ("आंबा", 0, 1, 15, 15),
	"Papaya": ("पपई", 0, 1, 6, 6),
}

SPRAY_VARIETIES = {
	"Pomegranate": [("Bhagwa", "भगवा"), ("Ganesh", "गणेश"), ("Arakta", "आरक्ता"), ("Mridula", "मृदुला")],
	"Grapes": [
		("Thompson Seedless", "थॉमसन सीडलेस"),
		("Sonaka", "सोनाका"),
		("Sharad Seedless", "शरद सीडलेस"),
		("Tas-A-Ganesh", "तास-ए-गणेश"),
		("Super Sonaka", "सुपर सोनाका"),
	],
	"Onion": [
		("N-53", "एन-५३"),
		("Bhima Super", "भीमा सुपर"),
		("Bhima Kiran", "भीमा किरण"),
		("Agrifound Light Red", "ॲग्रीफाउंड लाईट रेड"),
	],
	"Sugarcane": [
		("Co-86032", "को-८६०३२"),
		("Co-265", "को-२६५"),
		("Co-0238", "को-०२३८"),
		("Co-94012", "को-९४०१२"),
		("VSI-8005", "व्हीएसआय-८००५"),
	],
	"Tomato": [("Hybrid", "संकरित"), ("Pusa Ruby", "पुसा रुबी"), ("Arka Vikas", "अर्का विकास")],
	"Banana": [("Grand Naine", "ग्रँड नैन"), ("Robusta", "रोबस्टा"), ("Basrai", "बसराई")],
	"Soybean": [
		("JS-335", "जेएस-३३५"),
		("JS-9305", "जेएस-९३०५"),
		("MAUS-71", "मौस-७१"),
		("KDS-726", "केडीएस-७२६"),
	],
	"Cotton": [("Bt Cotton", "बीटी कापूस"), ("Desi (non-Bt)", "देशी (नॉन-बीटी)")],
	"Maize": [("Hybrid Maize", "संकरित मका"), ("Sweet Corn", "स्वीट कॉर्न"), ("Local", "स्थानिक")],
	"Wheat": [
		("HD-2189", "एचडी-२१८९"),
		("Lok-1", "लोक-१"),
		("Trimbak (NIAW-301)", "त्र्यंबक (NIAW-301)"),
		("HD-2967", "एचडी-२९६७"),
	],
}

BASAL_VARIETIES = {
	"Pomegranate": ["Bhagwa", "Ganesh", "Arakta", "Mridula", "Ruby", "Super Bhagwa"],
	"Banana": ["Grand Naine (G9)", "Robusta", "Shrimanti", "Red Banana", "Yelakki", "Basrai"],
	"Guava": ["Lalit", "Allahabad Safeda", "Taiwan Pink", "VNR Bihi", "Sardar (L-49)", "Thai Guava"],
	"Mango": ["Kesar", "Alphonso (Hapus)", "Totapuri", "Dasheri", "Langra", "Amrapali", "Mallika"],
	"Papaya": ["Taiwan 786", "Red Lady", "Pusa Dwarf", "Washington", "Coorg Honey Dew"],
}

SPRAY_EQUIPMENT = [
	("HTP Pump", "एचटीपी पंप", 200),
	("Blower", "ब्लोअर", 400),
	("Battery operated sprayer", "बॅटरी स्प्रेयर", 16),
]

_ML, _GM = "ml / L", "gm / L"
SPRAY_PRODUCTS = {
	"Insecticides": [
		("Delegate", "डेलीगेट", _ML),
		("Curacron", "क्युराक्रॉन", _ML),
		("Pride", "प्राईड", _ML),
		("Confidor", "कॉन्फिडोर", _ML),
	],
	"Biopesticides": [("MBV 16", "एमबीव्ही १६", _ML), ("Nemashakti", "नेमाशक्ती", _ML)],
	"Fungicides": [
		("M-45", "एम-४५", _GM),
		("Bavistin", "बाविस्टीन", _GM),
		("Z-78", "झेड-७८", _GM),
		("Cuman L", "क्युमन एल", _ML),
	],
	"Bio fungicides": [
		("Trichoderma", "ट्रायकोडर्मा", _GM),
		("Paecilomyces", "पेसिलोमायसीस", _GM),
		("Pseudomonas", "स्यूडोमोनास", _GM),
	],
	"Herbicides": [("Round Up", "राऊंड अप", _ML), ("Mera-71", "मेरा-७१", _GM)],
	"Sprayers & adjuvants": [("SSPN 1149", "एसएसपीएन 1149", _ML), ("Nanoreach", "नॅनोरिच", _ML)],
}

# FERT0: (name, pack kg, contains, price per bag)
FERTILIZERS = [
	("ORGANIC 4 G - NPK", 25, "NPK 10 %", 1250),
	("ORGANIC NPK", 25, "ORGANIC NITROGEN, PHOSPHORUS, POTASH", 1250),
	("BIO POTASH", 25, "ORGANIC POTASH + AMINO", 1250),
	("BIO PHOS", 25, "BIO AVAILABLE PHOSPHORUS 10 %", 2680),
	("AISHWARYA", 25, "ORGANIC CARBON 10 % + VITAMINS", 2500),
	("MEGACAL", 25, "MICRO + MACRO NUTRIENTS + AMINO", 1340),
	("FISH MEAL", 20, "PHOSPHORUS + CALCIUM", 2530),
	("FISH BONE MEAL", 20, "FISH MEAL", 2530),
	("NEEM POWER", 20, "PURE NEEM POWDER", 1450),
	("NEEM SUPER", 20, "NEEM POWDER", 1450),
	("AJAY NEEM", 25, "PURE NEEM POWDER", 2600),
	("YARA MILLA COMPLEX", 25, "12:11:18 + MGO + SULPHUR", 2550),
	("YARAMILA", 25, "NPK 12:11:18", 2500),
	("EKKAPHOS", 50, "PROM", 850),
	("KALICHKRA", 1, "METARHIZIUM ANISOPLIAE", 270),
	("PROTEGO", 1, "TRICHODERMA HARZIANUM", 260),
	("NEMATOFREE PLUS", 1, "VERTICILLIUM CHLAMYDOSPORIUM", 310),
	("ZYTONIC KIT", 8, "MYCORRHIZA + NPK + ZINC", 2350),
	("ZYTONIC MINI KIT", 8, "MYCORRHIZA, NPK & ZINC SOLUBILIZING BACTERIA", 2350),
	("ZYTONIC M", 5, "MYCORRHIZA", 1500),
]

# TPL: (fertilizer, gm/plant, pack override, contains override, cost override)
# Overrides reproduce the prototype exactly, including Mango's BIO POTASH row
# that carries the "BIO AVAILABLE PHOSPHORUS 10 %" description from the Excel.
FERTILIZER_TEMPLATES = {
	"Mango": [
		("ORGANIC 4 G - NPK", 50),
		("BIO POTASH", 50, 25, "BIO AVAILABLE PHOSPHORUS 10 %"),
		("MEGACAL", 50),
		("FISH MEAL", 50),
		("NEEM POWER", 50),
		("YARA MILLA COMPLEX", 100),
		("KALICHKRA", 4, 1, None, 280),
		("ZYTONIC KIT", 20),
	],
	"Pomegranate": [
		("EKKAPHOS", 200),
		("YARAMILA", 24),
		("FISH BONE MEAL", 20),
		("AJAY NEEM", 20, 20, None, 1450),
		("ZYTONIC MINI KIT", 5),
		("PROTEGO", 5),
		("KALICHKRA", 5),
		("NEMATOFREE PLUS", 5),
		("ORGANIC NPK", 50),
	],
	"Papaya": [
		("EKKAPHOS", 200),
		("YARAMILA", 15),
		("FISH BONE MEAL", 15),
		("NEEM SUPER", 15),
		("ZYTONIC MINI KIT", 5),
		("PROTEGO", 5),
		("KALICHKRA", 5),
		("NEMATOFREE PLUS", 5),
		("ORGANIC NPK", 48),
	],
	# Banana and Guava deliberately have no template in the reference.
}
