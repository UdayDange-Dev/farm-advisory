// Copyright (c) 2026, Uday Dange and contributors
//
// Crop Consultation form — the Agrismart Crop Consultancy field app.
// Every figure, check and advisory card comes from
// farm_advisory.api.preview_crop_consultation (the same Python as validate());
// this script only collects input, captures GPS and shows the result.
// Nothing is kept in browser storage: the record is the Crop Consultation itself.

const CC_PF = "Crop Consultation Report";
const CC_PANELS = ["advisory_html", "data_checks", "followup_plan", "ndvi_chart"];
const CC_PREVIEW = {
	method: "farm_advisory.api.preview_crop_consultation",
	tables: ["crop_blocks"],
	after(frm, msg) {
		const panels = msg.panels || {};
		CC_PANELS.forEach((f) => {
			const field = frm.get_field(f);
			if (field) field.$wrapper.html(panels[f] || "");
		});
	},
};

// fields whose change alters a calculation, check or advisory card
const CC_RECALC_FIELDS = [
	"visit_date", "report_language", "first_name", "last_name", "mobile_no", "latitude", "longitude",
	"farm_area_unit", "total_area", "irrigated_area", "non_irrigated_area", "family_area",
	"dripper_lph", "water_ec", "water_bicarbonate",
	"soil_n", "soil_p", "soil_k", "soil_organic_carbon", "soil_ph", "pest_risk",
	"rain_probability", "wind_speed", "humidity", "temperature",
	"irr_block_no", "irr_drippers_per_plant", "irr_total_drippers", "irr_hours", "irr_required_per_plant",
];

// Marathi labels from the prototype, used by the language switch
const CC_LABELS = {
	parent: {
		visit_tab: "भेट व शेतकरी", visit_date: "भेट तारीख", consultant: "ॲग्रीस्मार्ट सल्लागार",
		branch: "शाखा", status: "शिफारस स्थिती", next_visit: "पुढील भेट",
		farmer_section: "शेतकरी माहिती", customer: "ग्राहकाचे नाव", first_name: "पहिले नाव",
		middle_name: "वडिलांचे / मधले नाव", last_name: "आडनाव", farmer_name: "शेतकऱ्याचे नाव",
		village: "गाव", taluka: "तालुका", district: "जिल्हा", state: "राज्य", pin_code: "पिन कोड",
		landmark: "खूण", mobile_no: "मोबाईल नंबर", whatsapp_same_as_mobile: "मोबाईल नंबर प्रमाणेच",
		whatsapp_no: "व्हॉट्सअ‍ॅप नंबर", email_id: "ई-मेल आयडी", address_section: "पत्ता",
		customer_address: "ग्राहकाचा पत्ता", address_display: "पत्ता",
		gps_section: "GPS शेत ठिकाण", latitude: "अक्षांश", longitude: "रेखांश", gps_accuracy: "अचूकता (मी)",
		farm_tab: "शेत व पिके", farm_area_section: "शेत क्षेत्र", farm_area_unit: "क्षेत्र एकक",
		total_area: "एकूण क्षेत्र", irrigated_area: "सिंचित", non_irrigated_area: "कोरडवाहू",
		area_7_12: "७/१२ नुसार क्षेत्र", area_8a: "८अ नुसार क्षेत्र", family_area: "कुटुंबाचे एकूण क्षेत्र",
		crop_area_total: "पीक विभाग क्षेत्र", landholder_area_total: "जमीनधारक क्षेत्र",
		total_plants: "एकूण झाडे", crop_blocks_section: "पीक विभाग", crop_blocks: "पीक विभाग",
		landholders_section: "कुटुंबातील जमीनधारक / सहमालक", documents_section: "नकाशे व जमीन कागदपत्रे",
		water_tab: "पाणी व साधने", water_sources_section: "सिंचन स्रोत", pumps_section: "विद्युत पंप",
		drip_section: "ठिबक / सिंचन व्यवस्था", drip_area: "ठिबकखालील क्षेत्र (एकर)",
		dripper_lph: "ड्रिपर विसर्ग (LPH)", water_quality_section: "पाण्याची गुणवत्ता",
		infrastructure_section: "पायाभूत सुविधा व यंत्रे",
		diagnosis_tab: "निदान", problems_section: "निदान प्रकरणे", history_section: "अलीकडील इतिहास",
		last_pesticide: "शेवटचे कीटकनाशक / बुरशीनाशक", last_fertilizer: "शेवटचे खत / सूक्ष्म अन्नद्रव्य",
		last_irrigation: "शेवटचे सिंचन", recent_rainfall: "अलीकडील पाऊस",
		previous_pest_disease: "आधीची कीड / रोग", photos_section: "फोटो",
		satellite_tab: "उपग्रह (Satyukt)", ndvi_section: "पीक आरोग्य (NDVI) कल",
		ndvi_status: "पीक आरोग्य", soil_section: "मृदा माहिती", soil_n: "नत्र (N)", soil_p: "स्फुरद (P)",
		soil_k: "पालाश (K)", soil_organic_carbon: "सेंद्रिय कर्ब", soil_ph: "मातीचा pH",
		soil_moisture: "मातीतील ओलावा", pest_risk: "कीड / रोग धोका",
		weather_section: "हवामान (पुढील २४–४८ तास)", rain_probability: "पावसाची शक्यता %",
		wind_speed: "वारा (किमी/तास)", humidity: "आर्द्रता %", temperature: "तापमान °C",
		spray_decision: "फवारणी निर्णय",
		advisory_tab: "सल्ला व शिफारस", advisory_section: "सल्ला इंजिन",
		irrigation_section: "सिंचन कॅल्क्युलेटर", irr_block_no: "पीक विभाग क्र.",
		irr_drippers_per_plant: "प्रति झाड ड्रिपर", irr_total_drippers: "किंवा एकूण ड्रिपर",
		irr_hours: "तास प्रति सिंचन", irr_required_per_plant: "आवश्यक लि. / झाड / सिंचन (ऐच्छिक)",
		irr_flow_lph: "प्रवाह (लि./तास)", irr_water_l: "प्रति सिंचन पाणी (लि.)",
		irr_water_per_plant: "प्रति झाड (लि.)", irr_depth_mm: "विभागावर खोली (मिमी)",
		prescription_section: "शिफारस (तज्ज्ञ)", agronomist: "मान्यता देणारे तज्ज्ञ",
		prescription_items: "उत्पादने / खते", agronomic_notes: "कृषी सूचना, सिंचन व बिगर-रासायनिक उपाय",
		followup_section: "पाठपुरावा नोंद", followups: "पाठपुरावा",
	},
	crop_blocks: {
		block_no: "विभाग क्र.", crop: "पीक", variety: "वाण", crop_stage: "पीक अवस्था", bahar: "बहार",
		area: "क्षेत्र", plant_count: "झाडांची संख्या", plantation_date: "लागवडीची तारीख",
	},
	problems: {
		block_no: "पीक विभाग क्र.", problem_type: "समस्येचा प्रकार", affected_part: "बाधित भाग",
		severity: "तीव्रता", affected_pct: "बाधित क्षेत्र %", observation: "लक्षणे / निरीक्षण",
	},
	prescription_items: {
		category: "प्रकार", product: "उत्पादन / घटक", dose: "मात्रा", dose_unit: "एकक",
		per: "प्रति", method: "पद्धत",
	},
};
const CC_TABLES = {
	crop_blocks: "Crop Consultation Block",
	problems: "Crop Consultation Problem",
	prescription_items: "Crop Consultation Prescription",
};

const CC_CSS = `
.fa-cc{font-size:13px}
.fa-cc-chip{display:inline-block;border:1px solid var(--border-color);border-radius:12px;padding:2px 10px;margin:2px 4px 2px 0;background:var(--subtle-fg)}
.fa-cc-note{border-radius:8px;padding:6px 10px;margin:6px 0;background:var(--green-50,#eef8f1);color:var(--text-color)}
.fa-cc-note.warn{background:var(--yellow-50,#fff8e1)}
.fa-cc-note.bad{background:var(--red-50,#fdecea)}
.fa-cc-card{border:1px solid var(--border-color);border-left:4px solid var(--green-500,#2f8b68);border-radius:8px;padding:8px 12px;margin:8px 0}
.fa-cc-card.warn{border-left-color:var(--yellow-500,#d4a017)}
.fa-cc-card.bad{border-left-color:var(--red-500,#c0392b)}
.fa-cc-card h4{font-size:14px;margin:0 0 6px}
.fa-cc-card ul{margin:0;padding-left:18px}
.fa-cc-w5{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin-bottom:6px;font-size:12px}
@media (max-width:640px){.fa-cc-w5{grid-template-columns:1fr}.fa-cc-card{padding:6px 8px}}
`;

function cc_recalc(frm) {
	farm_advisory.preview(frm, CC_PREVIEW);
}

function cc_style() {
	if (document.getElementById("fa-cc-style")) return;
	const s = document.createElement("style");
	s.id = "fa-cc-style";
	s.textContent = CC_CSS;
	document.head.appendChild(s);
}

function cc_gps_map(frm) {
	const f = frm.get_field("gps_map");
	if (!f) return;
	const { latitude: lat, longitude: lon } = frm.doc;
	if (!lat && !lon) return f.$wrapper.html("");
	const q = `${lat},${lon}`;
	f.$wrapper.html(
		`<a class="btn btn-xs btn-default" target="_blank" rel="noopener noreferrer"
			href="https://www.google.com/maps?q=${encodeURIComponent(q)}">${__("Open in Maps")}</a>`
	);
}

function cc_capture_gps(frm) {
	if (!navigator.geolocation) {
		frappe.msgprint(__("This device or browser cannot read the location."));
		return;
	}
	frappe.show_alert({ message: __("Reading GPS location…"), indicator: "blue" });
	navigator.geolocation.getCurrentPosition(
		async (pos) => {
			const c = pos.coords;
			await frm.set_value({
				latitude: Number(c.latitude.toFixed(6)),
				longitude: Number(c.longitude.toFixed(6)),
				gps_accuracy: Math.round(c.accuracy * 10) / 10,
				gps_captured_on: frappe.datetime.now_datetime(),
			});
			frappe.show_alert({ message: __("GPS captured (±{0} m)", [Math.round(c.accuracy)]), indicator: "green" });
		},
		(err) => frappe.msgprint(__("Could not read the location: {0}", [err.message])),
		{ enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
	);
}

function cc_import_satyukt(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Import Satyukt JSON"),
		fields: [
			{
				fieldname: "json", fieldtype: "Code", options: "JSON", reqd: 1,
				label: __("Paste Satyukt JSON"),
				description: __('Example: {"ndvi":[{"date":"2026-08-01","v":0.62}],"soil":{"n":"Low","p":"Medium","k":"High","soc":"Low","ph":7.8},"moisture":"Medium","pest":"Moderate","weather":{"rain":20,"wind":8,"hum":70,"temp":31}}'),
			},
		],
		primary_action_label: __("Import"),
		async primary_action(v) {
			const r = await frappe.call({ method: "farm_advisory.api.parse_satyukt_json", args: { content: v.json } });
			const { values = {}, ndvi = [] } = r.message || {};
			const apply = async () => {
				await frm.set_value(values);
				if (ndvi.length) {
					frm.clear_table("ndvi_readings");
					ndvi.forEach((row) => frm.add_child("ndvi_readings", row));
					frm.refresh_field("ndvi_readings");
				}
				d.hide();
				frappe.show_alert({ message: __("Satyukt data imported – review before saving"), indicator: "green" });
				cc_recalc(frm);
			};
			if (ndvi.length && (frm.doc.ndvi_readings || []).length) {
				frappe.confirm(__("Replace the {0} NDVI reading(s) already on this visit?", [frm.doc.ndvi_readings.length]), apply);
			} else {
				apply();
			}
		},
	});
	d.show();
}

const cc_handlers = {
	setup(frm) {
		frm.set_query("variety", "crop_blocks", (doc, cdt, cdn) => ({
			filters: { crop: locals[cdt][cdn].crop || "" },
		}));
		frm.set_query("item", "prescription_items", () => ({ filters: { disabled: 0 } }));
		farm_advisory.setup_address_query(frm);
	},

	onload(frm) {
		cc_style();
		if (!frm.is_new()) return;
		frappe.db.get_doc("Farm Advisory Settings").then((s) => {
			if (!frm.doc.branch && s.default_branch) frm.set_value("branch", s.default_branch);
			if (s.default_report_language && frm.doc.report_language !== s.default_report_language) {
				frm.set_value("report_language", s.default_report_language);
			}
		});
		if (!(frm.doc.crop_blocks || []).length) {
			frm.add_child("crop_blocks", { block_no: 1 });
			frm.refresh_field("crop_blocks");
		}
	},

	refresh(frm) {
		cc_style();
		frm.trigger("apply_language");
		cc_gps_map(frm);
		cc_recalc(frm);

		frm.add_custom_button(__("Capture GPS"), () => cc_capture_gps(frm));
		if (!frm.doc.customer) {
			frm.add_custom_button(__("Create Customer"), () => farm_advisory.create_customer(frm));
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Add Follow-up"), () => {
				frm.add_child("followups", { followup_date: frappe.datetime.get_today() });
				frm.refresh_field("followups");
				frm.scroll_to_field("followups");
			});
		}
		frm.add_custom_button(__("Print"), () => farm_advisory.print(frm, CC_PF), __("Report"));
		frm.add_custom_button(__("Download PDF"), () => farm_advisory.download_pdf(frm, CC_PF), __("Report"));
		frm.add_custom_button(__("WhatsApp"), () => farm_advisory.share_whatsapp(frm, CC_PF), __("Report"));
	},

	apply_language(frm) {
		farm_advisory.apply_labels(frm, CC_LABELS, farm_advisory.lang_key(frm.doc.report_language), CC_TABLES);
	},

	report_language(frm) {
		frm.trigger("apply_language");
		cc_recalc(frm);
	},

	satellite_import(frm) { cc_import_satyukt(frm); },

	// ── farmer ─────────────────────────────────────────────────────────
	customer(frm) { farm_advisory.fill_from_customer(frm); },
	customer_address(frm) { farm_advisory.fill_address(frm); },
	mobile_no(frm) { farm_advisory.sync_whatsapp(frm); cc_recalc(frm); },
	whatsapp_same_as_mobile(frm) { farm_advisory.sync_whatsapp(frm); },
	latitude(frm) { cc_gps_map(frm); cc_recalc(frm); },
	longitude(frm) { cc_gps_map(frm); cc_recalc(frm); },

	// ── tables ─────────────────────────────────────────────────────────
	crop_blocks_remove: cc_recalc,
	landholders_remove: cc_recalc,
	problems_remove: cc_recalc,
	photos_remove: cc_recalc,
	ndvi_readings_remove: cc_recalc,
	photos_add: cc_recalc,
};
CC_RECALC_FIELDS.forEach((f) => {
	if (!cc_handlers[f]) cc_handlers[f] = cc_recalc;
});
frappe.ui.form.on("Crop Consultation", cc_handlers);

frappe.ui.form.on("Crop Consultation Block", {
	crop(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row.variety) frappe.model.set_value(cdt, cdn, "variety", "");
		if (!row.crop) return cc_recalc(frm);
		frappe.db.get_value("Farm Crop", row.crop, ["default_row_spacing", "default_plant_spacing"]).then((r) => {
			const c = r.message || {};
			// fill the crop's usual spacing only into empty fields; typed values are kept
			if (!row.row_spacing && c.default_row_spacing) row.row_spacing = c.default_row_spacing;
			if (!row.plant_spacing && c.default_plant_spacing) row.plant_spacing = c.default_plant_spacing;
			frm.refresh_field("crop_blocks");
			cc_recalc(frm);
		});
	},
	plant_count(frm, cdt, cdn) {
		// only a person typing fires this — the preview writes the field silently
		const row = locals[cdt][cdn];
		if (!row.plants_manual) frappe.model.set_value(cdt, cdn, "plants_manual", 1);
		cc_recalc(frm);
	},
	variety: cc_recalc,
	crop_stage: cc_recalc,
	plantation_date: cc_recalc,
	area: cc_recalc,
	area_unit: cc_recalc,
	row_spacing: cc_recalc,
	plant_spacing: cc_recalc,
	spacing_unit: cc_recalc,
	plants_manual: cc_recalc,
});

frappe.ui.form.on("Crop Consultation Landholder", { area: cc_recalc });

frappe.ui.form.on("Crop Consultation Problem", {
	block_no: cc_recalc,
	problem_type: cc_recalc,
	affected_part: cc_recalc,
	severity: cc_recalc,
	affected_pct: cc_recalc,
	observation: cc_recalc,
});

frappe.ui.form.on("Crop Consultation NDVI", { reading_date: cc_recalc, ndvi: cc_recalc });

frappe.ui.form.on("Crop Consultation Prescription", {
	item(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item || row.product) return;
		frappe.db.get_value("Item", row.item, "item_name").then((r) => {
			frappe.model.set_value(cdt, cdn, "product", (r.message || {}).item_name || row.item);
		});
	},
});
