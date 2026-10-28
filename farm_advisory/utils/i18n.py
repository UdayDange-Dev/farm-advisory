"""English / Marathi labels for reports, previews and WhatsApp text.

Mirrors the Spray prototype's ``t(en, mr)``: in "both" mode a label shows as
``English / मराठी`` unless the two are identical. User-entered data (names,
products) is never translated automatically — masters carry a Marathi name.
"""

LANGUAGES = {"English + Marathi": "both", "English": "en", "Marathi": "mr"}


def lang_key(report_language):
	return LANGUAGES.get(report_language or "", "both")


def tr(en, mr=None, lang="both"):
	if lang == "en":
		return en
	if lang == "mr":
		return mr or en
	return f"{en} / {mr}" if mr and mr != en else en


# --- fixed option lists from the prototypes (stored value -> Marathi) ------ #
SPRAY_CATEGORIES = {
	"Insecticides": "कीटकनाशके",
	"Biopesticides": "जैविक कीटकनाशके",
	"Fungicides": "बुरशीनाशके",
	"Bio fungicides": "जैविक बुरशीनाशके",
	"Herbicides": "तणनाशके",
	"Sprayers & adjuvants": "फवारणी सहायक (स्प्रेडर/स्टिकर)",
}

BAHAR = {
	"Not applicable": "लागू नाही",
	"Ambe Bahar": "आंबे बहार",
	"Mrig Bahar": "मृग बहार",
	"Hasta Bahar": "हस्त बहार",
	"Foundation pruning": "पायाभूत छाटणी",
	"Fruit pruning": "फळ छाटणी",
}

AREA_UNITS = {"Acre": "एकर", "Guntha": "गुंठा", "Hectare": "हेक्टर"}
SPACING_UNITS = {"Feet": "फूट", "Metre": "मीटर"}
WATER_BASIS = {
	"Litres per acre": "लिटर प्रति एकर",
	"Litres per plant": "लिटर प्रति झाड",
	"Total water (manual)": "एकूण पाणी (स्वतः)",
}
DOSE_UNITS = {"ml / L": "मिली / लि.", "gm / L": "ग्रॅम / लि.", "ppm (mg/L)": "ppm (मिग्रॅ/लि.)"}


def opt(value, mapping, lang):
	"""Translate a fixed Select value with one of the maps above."""
	if not value:
		return ""
	return tr(value, mapping.get(value), lang)


def master(en, mr, lang):
	"""A master record's own English and Marathi names."""
	return tr(en or "", mr or en or "", lang)
