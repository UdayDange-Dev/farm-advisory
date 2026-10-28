// Copyright (c) 2026, Uday Dange and contributors
//
// Spray Schedule form — the फवारणी वेळापत्रक calculator.
// Every figure is computed by farm_advisory.api.preview_spray_schedule (the
// same Python as validate()); this script only collects input and shows it.

const SPRAY_PF = "Spray Schedule Report";
const SPRAY_PREVIEW = {
	method: "farm_advisory.api.preview_spray_schedule",
	tables: ["sprays", "products"],
	html_field: "schedule_preview",
};
const WATER_DEFAULTS = { "Litres per acre": 200, "Litres per plant": 1, "Total water (manual)": 0 };

// Marathi labels from the prototype, used by the language switch
const SPRAY_LABELS = {
	parent: {
		branch: "शाखा", posting_date: "तारीख",
		customer: "शेतकरी (ग्राहक)", first_name: "पहिले नाव", middle_name: "वडिलांचे / मधले नाव",
		last_name: "आडनाव", farmer_name: "शेतकऱ्याचे नाव", village: "गाव", taluka: "तालुका",
		district: "जिल्हा", state: "राज्य", pin_code: "पिन कोड", mobile_no: "मोबाईल नंबर",
		whatsapp_same_as_mobile: "मोबाईल नंबर प्रमाणेच", whatsapp_no: "व्हॉट्सअ‍ॅप नंबर",
		email_id: "ई-मेल आयडी", crop: "पीक", variety: "वाण", plantation_date: "लागवडीची तारीख",
		crop_age: "पिकाचे वय", bahar: "बहार / छाटणी", bahar_date: "बहार धरल्याची तारीख",
		bahar_age: "बहार धरून झालेले दिवस", area: "क्षेत्र", area_unit: "क्षेत्र एकक",
		area_acre: "क्षेत्र (एकर)", spacing_unit: "अंतर एकक", row_spacing: "ओळीतील अंतर",
		plant_spacing: "झाडातील अंतर", plant_count: "झाडांची संख्या (क्षेत्र ÷ अंतर)",
		plants_manual: "झाडांची संख्या स्वतः भरली", water_basis: "पाणी मोजण्याची पद्धत",
		water_value: "पाणी", total_water: "एकूण पाणी (लिटर)", spray_equipment: "फवारणी यंत्र प्रकार",
		tank_capacity: "टाकी क्षमता (लिटर)", tanks_required: "टाक्या (दशांश)",
		tank_loads: "लागणाऱ्या टाक्या", sprays: "फवारण्या", products: "उत्पादने",
		grand_total: "एकूण रक्कम (प्रमाण × दर)", grand_pack_total: "पूर्ण पॅकनुसार किंमत",
	},
	sprays: { spray_no: "फवारणी क्र.", spray_date: "फवारणी तारीख", spray_total: "फवारणी एकूण",
		spray_pack_total: "पूर्ण पॅकनुसार किंमत" },
	products: { spray_no: "फवारणी क्र.", category: "प्रकार", product: "उत्पादन", dose: "मात्रा",
		dose_unit: "एकक", rate: "दर ₹ प्रति लि. / किलो", total_qty: "एकूण लागणारे",
		per_tank_qty: "प्रति टाकी", pack_suggestion: "पॅक सुचवणी", amount: "रक्कम" },
};

function spray_recalc(frm) {
	farm_advisory.preview(frm, SPRAY_PREVIEW);
}

function max_spray_no(frm) {
	return Math.max(0, ...(frm.doc.sprays || []).map((s) => s.spray_no || 0));
}

function add_spray(frm, copy_previous) {
	const prev = max_spray_no(frm);
	const row = frm.add_child("sprays", { spray_no: prev + 1 });
	if (copy_previous && prev) {
		(frm.doc.products || [])
			.filter((p) => p.spray_no === prev)
			.forEach((p) => {
				frm.add_child("products", {
					spray_no: prev + 1, category: p.category, product: p.product,
					product_name: p.product_name, product_name_mr: p.product_name_mr,
					dose: p.dose, dose_unit: p.dose_unit, rate: p.rate,
				});
			});
		frappe.show_alert({
			message: __("Copied products from previous spray – edit as needed"),
			indicator: "green",
		});
	}
	frm.refresh_field("sprays");
	frm.refresh_field("products");
	spray_recalc(frm);
	return row;
}

function set_first_product(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.category) return;
	frappe.call({
		method: "farm_advisory.api.get_first_spray_product",
		args: { category: row.category },
	}).then((r) => {
		const p = r.message;
		if (!p) return;
		frappe.model.set_value(cdt, cdn, "product", p.name);
	});
}

frappe.ui.form.on("Spray Schedule", {
	setup(frm) {
		frm.set_query("crop", () => ({ filters: { used_in_spray: 1 } }));
		frm.set_query("variety", () => ({
			filters: { crop: frm.doc.crop || "", used_in_spray: 1 },
		}));
		frm.set_query("product", "products", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			return { filters: { category: row.category || "", is_active: 1 } };
		});
	},

	onload(frm) {
		if (!frm.is_new()) return;
		frappe.db.get_doc("Farm Advisory Settings").then((s) => {
			if (!frm.doc.branch && s.default_branch) frm.set_value("branch", s.default_branch);
			if (s.default_report_language && frm.doc.report_language !== s.default_report_language) {
				frm.set_value("report_language", s.default_report_language);
			}
		});
		if (!(frm.doc.sprays || []).length) {
			// the prototype opens with Spray 1 and one product row
			add_spray(frm, false);
			const p = frm.add_child("products", { spray_no: 1, category: "Insecticides" });
			frm.refresh_field("products");
			set_first_product(frm, p.doctype, p.name);
		}
	},

	refresh(frm) {
		frm.trigger("apply_language");
		spray_recalc(frm);

		frm.add_custom_button(__("Add Spray"), () => add_spray(frm, true));
		if (!frm.doc.customer) {
			frm.add_custom_button(__("Create Customer"), () => frm.trigger("create_customer"));
		}
		frm.add_custom_button(__("Print"), () => farm_advisory.print(frm, SPRAY_PF), __("Report"));
		frm.add_custom_button(__("Download PDF"), () => farm_advisory.download_pdf(frm, SPRAY_PF), __("Report"));
		frm.add_custom_button(__("WhatsApp"), () => farm_advisory.share_whatsapp(frm, SPRAY_PF), __("Report"));
	},

	report_language(frm) {
		frm.trigger("apply_language");
		spray_recalc(frm);
	},

	apply_language(frm) {
		farm_advisory.apply_labels(frm, SPRAY_LABELS, farm_advisory.lang_key(frm.doc.report_language),
			{ sprays: "Spray Schedule Spray", products: "Spray Schedule Product" });
	},

	// ── farmer ─────────────────────────────────────────────────────────
	customer(frm) { farm_advisory.fill_from_customer(frm); },
	create_customer(frm) { farm_advisory.create_customer(frm); },
	mobile_no(frm) { farm_advisory.sync_whatsapp(frm); spray_recalc(frm); },
	whatsapp_same_as_mobile(frm) { farm_advisory.sync_whatsapp(frm); spray_recalc(frm); },
	first_name: spray_recalc,
	middle_name: spray_recalc,
	last_name: spray_recalc,
	village: spray_recalc,
	taluka: spray_recalc,
	district: spray_recalc,
	state: spray_recalc,
	pin_code: spray_recalc,
	email_id: spray_recalc,
	whatsapp_no: spray_recalc,
	branch: spray_recalc,

	// ── crop & plot ────────────────────────────────────────────────────
	crop(frm) {
		if (frm.doc.variety) frm.set_value("variety", "");
		spray_recalc(frm);
	},
	variety: spray_recalc,
	plantation_date: spray_recalc,
	bahar: spray_recalc,
	bahar_date: spray_recalc,
	area: spray_recalc,
	area_unit: spray_recalc,
	spacing_unit: spray_recalc,
	row_spacing: spray_recalc,
	plant_spacing: spray_recalc,
	plant_count(frm) {
		// only a person typing fires this — the preview writes the field silently
		if (!frm.doc.plants_manual) frm.set_value("plants_manual", 1);
		spray_recalc(frm);
	},
	plants_manual: spray_recalc,
	water_basis(frm) {
		const v = WATER_DEFAULTS[frm.doc.water_basis];
		frm.set_value("water_value", v || null);
		spray_recalc(frm);
	},
	water_value: spray_recalc,
	spray_equipment(frm) {
		if (!frm.doc.spray_equipment) return spray_recalc(frm);
		frappe.db.get_value("Spray Equipment", frm.doc.spray_equipment, "tank_capacity").then((r) => {
			const cap = (r.message || {}).tank_capacity;
			if (cap) frm.set_value("tank_capacity", cap);
			spray_recalc(frm);
		});
	},
	tank_capacity: spray_recalc,

	// ── tables ─────────────────────────────────────────────────────────
	sprays_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.spray_no) {
			row.spray_no = max_spray_no(frm) + 1;
			frm.refresh_field("sprays");
		}
		spray_recalc(frm);
	},
	sprays_remove(frm) {
		// a spray's products go with it, as "Remove spray" did in the prototype
		const live = new Set((frm.doc.sprays || []).map((s) => s.spray_no));
		const orphans = (frm.doc.products || []).filter((p) => !live.has(p.spray_no));
		if (orphans.length) {
			orphans.forEach((p) => frappe.model.clear_doc(p.doctype, p.name));
			frm.refresh_field("products");
			frappe.show_alert({ message: __("{0} product row(s) of the removed spray were removed",
				[orphans.length]), indicator: "orange" });
		}
		spray_recalc(frm);
	},
	products_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.spray_no) row.spray_no = max_spray_no(frm) || 1;
		if (!row.category) row.category = "Insecticides";
		frm.refresh_field("products");
		set_first_product(frm, cdt, cdn);
	},
	products_remove: spray_recalc,
});

frappe.ui.form.on("Spray Schedule Spray", {
	spray_date: spray_recalc,
});

frappe.ui.form.on("Spray Schedule Product", {
	category(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "product", "");
		set_first_product(frm, cdt, cdn);
	},
	product(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.product) return spray_recalc(frm);
		frappe.db.get_value("Spray Product", row.product,
			["product_name", "product_name_mr", "default_dose_unit", "category"]).then((r) => {
			const p = r.message || {};
			row.product_name = p.product_name;
			row.product_name_mr = p.product_name_mr;
			if (p.default_dose_unit) row.dose_unit = p.default_dose_unit;
			if (p.category && row.category !== p.category) row.category = p.category;
			frm.refresh_field("products");
			spray_recalc(frm);
		});
	},
	spray_no: spray_recalc,
	dose: spray_recalc,
	dose_unit: spray_recalc,
	rate: spray_recalc,
});
