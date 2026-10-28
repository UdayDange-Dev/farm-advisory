// Copyright (c) 2026, Uday Dange and contributors
//
// Shared helpers for the Spray Schedule and Basal Dose forms.
//
// The calculators feel live like the HTML prototypes, but every figure comes
// from the server: each edit sends the form to a whitelisted preview method
// that runs the same Python as validate(). The browser never does its own
// arithmetic, so a number cannot change the moment the user presses Save.
frappe.provide("farm_advisory");

(function () {
	const DEBOUNCE_MS = 300;

	/** Queue a preview; rapid edits collapse into one request. */
	farm_advisory.preview = function (frm, cfg) {
		clearTimeout(frm.__fa_timer);
		frm.__fa_timer = setTimeout(() => farm_advisory.run_preview(frm, cfg), DEBOUNCE_MS);
	};

	farm_advisory.run_preview = function (frm, cfg) {
		const seq = (frm.__fa_seq = (frm.__fa_seq || 0) + 1);
		return frappe
			.call({ method: cfg.method, args: { doc: frm.doc }, freeze: false })
			.then((r) => {
				// a later edit has already asked again — drop this stale answer
				if (seq !== frm.__fa_seq || !r || !r.message) return;
				farm_advisory.apply_preview(frm, r.message, cfg);
			});
	};

	/** Copy calculated values in without re-rendering grids (keeps focus while typing). */
	farm_advisory.apply_preview = function (frm, msg, cfg) {
		Object.entries(msg.parent || {}).forEach(([k, v]) => {
			if (frm.doc[k] !== v) {
				frm.doc[k] = v;
				frm.refresh_field(k);
			}
		});
		(cfg.tables || []).forEach((table) => {
			const data = msg[table] || {};
			const grid = frm.fields_dict[table] && frm.fields_dict[table].grid;
			(frm.doc[table] || []).forEach((row) => {
				const vals = data[row.name];
				if (!vals) return;
				Object.entries(vals).forEach(([k, v]) => {
					if (row[k] === v) return;
					row[k] = v;
					const grid_row = grid && grid.grid_rows_by_docname[row.name];
					if (grid_row) grid_row.refresh_field(k);
				});
			});
		});
		if (cfg.after) cfg.after(frm, msg);
		const html = cfg.html_field && frm.get_field(cfg.html_field);
		if (html) html.$wrapper.html(`<div style="overflow-x:auto">${msg.html || ""}</div>`);
	};

	/** Ensure the document is saved before printing or sharing it. */
	farm_advisory.ensure_saved = async function (frm) {
		if (frm.is_new() || frm.is_dirty()) {
			await frm.save();
		}
		return !frm.is_new();
	};

	farm_advisory.pdf_url = function (frm, print_format) {
		const q = new URLSearchParams({
			doctype: frm.doc.doctype,
			name: frm.doc.name,
			format: print_format,
			no_letterhead: 1,
		});
		return "/api/method/frappe.utils.print_format.download_pdf?" + q.toString();
	};

	farm_advisory.download_pdf = async function (frm, print_format) {
		if (!(await farm_advisory.ensure_saved(frm))) return;
		window.open(farm_advisory.pdf_url(frm, print_format));
	};

	farm_advisory.print = async function (frm, print_format) {
		if (!(await farm_advisory.ensure_saved(frm))) return;
		frappe.utils.print(frm.doc.doctype, frm.doc.name, print_format);
	};

	/**
	 * WhatsApp, as in the prototypes: share the PDF through the device's share
	 * sheet when the browser supports file sharing; otherwise download the PDF
	 * and open the WhatsApp chat with the text — the user attaches the file.
	 * wa.me links cannot carry attachments, so we never claim they do.
	 */
	farm_advisory.share_whatsapp = async function (frm, print_format) {
		if (!(await farm_advisory.ensure_saved(frm))) return;
		const r = await frappe.call({
			method: "farm_advisory.api.get_whatsapp_message",
			args: { doctype: frm.doc.doctype, name: frm.doc.name },
			freeze: true,
			freeze_message: __("Preparing PDF for WhatsApp…"),
		});
		const { number, text } = r.message || {};
		const wa_url = "https://wa.me/" + (number || "") + "?text=" + encodeURIComponent(text || "");
		const filename = `${frm.doc.name}.pdf`;

		let file = null;
		try {
			const res = await fetch(farm_advisory.pdf_url(frm, print_format), {
				headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			});
			const type = res.headers.get("content-type") || "";
			if (res.ok && type.includes("pdf")) {
				file = new File([await res.blob()], filename, { type: "application/pdf" });
			}
		} catch (e) {
			file = null;
		}

		if (file && navigator.canShare && navigator.canShare({ files: [file] })) {
			try {
				await navigator.share({ files: [file], title: frm.doc.name, text });
				return;
			} catch (e) {
				if (e && e.name === "AbortError") return;
			}
		}

		let message;
		if (file) {
			const a = document.createElement("a");
			a.href = URL.createObjectURL(file);
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
			message = __("The PDF has been downloaded. Attach it in the WhatsApp chat that opens.");
		} else {
			message = __("The PDF could not be generated here, so only the text will be sent.");
		}
		if (!number) message += "<br><br>" + __("No mobile / WhatsApp number on this record – choose the chat in WhatsApp.");
		const d = new frappe.ui.Dialog({
			title: __("Share on WhatsApp"),
			fields: [{ fieldtype: "HTML", options: `<p>${message}</p>` }],
			primary_action_label: __("Open WhatsApp"),
			primary_action() {
				window.open(wa_url, "_blank");
				d.hide();
			},
		});
		d.show();
	};

	/** Relabel form fields in English, Marathi or both (Spray prototype's language switch). */
	farm_advisory.apply_labels = function (frm, labels, lang, tables) {
		const t = (en, mr) =>
			lang === "en" ? en : lang === "mr" ? mr || en : mr && mr !== en ? `${en} / ${mr}` : en;
		frm.__fa_en = frm.__fa_en || {};
		Object.entries(labels.parent || {}).forEach(([f, mr]) => {
			const df = frappe.meta.get_docfield(frm.doctype, f);
			if (!df) return;
			if (!(f in frm.__fa_en)) frm.__fa_en[f] = df.label;
			frm.set_df_property(f, "label", t(__(frm.__fa_en[f]), mr));
		});
		Object.entries(tables || {}).forEach(([table, child]) => {
			const grid = frm.fields_dict[table] && frm.fields_dict[table].grid;
			if (!grid) return;
			Object.entries(labels[table] || {}).forEach(([f, mr]) => {
				const key = table + "." + f;
				const df = frappe.meta.get_docfield(child, f);
				if (!df) return;
				if (!(key in frm.__fa_en)) frm.__fa_en[key] = df.label;
				grid.update_docfield_property(f, "label", t(__(frm.__fa_en[key]), mr));
			});
		});
	};

	farm_advisory.lang_key = (v) => ({ English: "en", Marathi: "mr" })[v] || "both";

	// ── farmer = ERPNext Customer ─────────────────────────────────────
	farm_advisory.fill_from_customer = function (frm) {
		if (!frm.doc.customer) return;
		frappe.call({
			method: "farm_advisory.utils.farmer.get_farmer_details",
			args: { customer: frm.doc.customer },
		}).then((r) => {
			const v = r.message || {};
			Object.keys(v).forEach((k) => {
				if (v[k] !== undefined && v[k] !== null && v[k] !== "") frm.set_value(k, v[k]);
			});
		});
	};

	farm_advisory.create_customer = function (frm) {
		const d = frm.doc;
		if (!d.first_name) {
			frappe.msgprint(__("Enter the farmer's first name first."));
			return;
		}
		frappe.call({
			method: "farm_advisory.utils.farmer.create_customer",
			args: {
				first_name: d.first_name, middle_name: d.middle_name, last_name: d.last_name,
				mobile_no: d.mobile_no, email_id: d.email_id,
				whatsapp_no: d.whatsapp_same_as_mobile ? d.mobile_no : d.whatsapp_no,
				village: d.village, taluka: d.taluka, district: d.district, state: d.state,
				pin_code: d.pin_code,
			},
			freeze: true,
		}).then((r) => {
			const res = r.message || {};
			// set without firing the customer handler: the form already holds these details
			frm.doc.customer = res.customer;
			frm.refresh_field("customer");
			frm.dirty();
			frm.remove_custom_button(__("Create Customer"));
			frappe.show_alert({
				message: res.existing
					? __("Linked existing Customer {0} (same mobile number)", [res.customer])
					: __("Customer {0} created", [res.customer]),
				indicator: "green",
			});
		});
	};

	farm_advisory.sync_whatsapp = function (frm) {
		if (frm.doc.whatsapp_same_as_mobile && frm.doc.whatsapp_no !== frm.doc.mobile_no) {
			frm.set_value("whatsapp_no", frm.doc.mobile_no);
		}
	};

	// ── basal fertilizer templates (Farm Crop → Fertilizer Template) ───
	// One template per crop. It is saved through the Farm Crop document, so the
	// server's write permission and validation decide; this dialog only collects rows.
	const TEMPLATE_API = "farm_advisory.farm_advisory.doctype.farm_crop.farm_crop.";
	const TEMPLATE_ROW = "Farm Crop Fertilizer Template";
	const TEMPLATE_FIELDS = ["fertilizer", "rate", "rate_unit", "pack_kg", "cost_per_bag", "contains"];

	/**
	 * Open the template editor. ``crop`` fixes the crop (editing, or creating
	 * from Load Template); without it the user chooses one. ``opts.on_save(crop)``
	 * and ``opts.on_delete(crop)`` run after the server has saved.
	 */
	farm_advisory.template_editor = async function (crop, opts = {}) {
		await frappe.model.with_doctype(TEMPLATE_ROW);
		const units = frappe.meta.get_docfield(TEMPLATE_ROW, "rate_unit").options;
		const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
		let existing = 0;
		let can_write = false;

		const d = new frappe.ui.Dialog({
			title: crop ? __("Fertilizer Template: {0}", [crop]) : __("Add Template"),
			size: "extra-large",
			fields: [
				{ fieldname: "crop", fieldtype: "Link", options: "Farm Crop", label: __("Crop"), reqd: 1,
				  default: crop || "", read_only: crop ? 1 : 0,
				  get_query: () => ({ filters: { used_in_basal: 1 } }),
				  onchange: () => load(d.get_value("crop")) },
				{ fieldname: "status", fieldtype: "HTML" },
				{ fieldname: "rows", fieldtype: "Table", label: __("Fertilizers"), data: [], allow_bulk_edit: false,
				  fields: [
					{ fieldname: "fertilizer", fieldtype: "Link", options: "Farm Fertilizer", label: __("Fertilizer"),
					  reqd: 1, in_list_view: 1, columns: 3, get_query: () => ({ filters: { is_active: 1 } }) },
					{ fieldname: "rate", fieldtype: "Float", label: __("Rate"), reqd: 1, non_negative: 1,
					  in_list_view: 1, columns: 1 },
					{ fieldname: "rate_unit", fieldtype: "Select", label: __("Rate Unit"), options: units,
					  default: "gm / plant", reqd: 1, in_list_view: 1, columns: 2 },
					{ fieldname: "pack_kg", fieldtype: "Float", label: __("Package Size (kg)"), non_negative: 1,
					  in_list_view: 1, columns: 2, description: __("0 uses the fertilizer master's pack size.") },
					{ fieldname: "cost_per_bag", fieldtype: "Currency", label: __("Bag Price"), non_negative: 1,
					  in_list_view: 1, columns: 2, description: __("0 uses the fertilizer master's price.") },
					{ fieldname: "contains", fieldtype: "Data", label: __("Contains") },
				  ] },
				{ fieldname: "help", fieldtype: "HTML", options: `<p class="text-muted small">${__(
					"Enter the values of the approved fertilizer schedule. A Package Size or Bag Price of 0 uses the value in the fertilizer master; if the master has none, saving asks for it.")}</p>` },
			],
			primary_action_label: __("Save Template"),
			primary_action: save,
			secondary_action_label: __("Delete Template"),
			secondary_action: remove,
		});

		function set_rows(rows) {
			d.fields_dict.rows.df.data = rows.map((r) => {
				const row = {};
				TEMPLATE_FIELDS.forEach((f) => (row[f] = r[f]));
				return row;
			});
			d.fields_dict.rows.grid.refresh();
		}

		function show_status(c) {
			const msg = !c ? __("Choose a crop.")
				: !can_write ? __("You can view this template. Only a Farm Advisory Manager can change it.")
				: existing ? __("{0} already has a template with {1} fertilizer(s). Saving replaces it.", [esc(c), existing])
				: __("{0} has no template yet. Add its fertilizers below.", [esc(c)]);
			d.fields_dict.status.$wrapper.html(`<div class="alert ${existing || !c ? "alert-info" : "alert-warning"} small">${msg}</div>`);
			d.get_primary_btn().toggle(!!c && can_write);
			d.get_secondary_btn().toggle(!!c && can_write && existing > 0);
		}

		async function load(c) {
			existing = 0;
			if (!c) {
				set_rows([]);
				return show_status(c);
			}
			// a crop that has a template opens it for editing; another crop's rows are never copied in
			const r = await frappe.call({ method: TEMPLATE_API + "get_template", args: { crop: c } });
			const t = r.message || {};
			existing = (t.rows || []).length;
			can_write = !!t.can_write;
			set_rows(t.rows || []);
			show_status(c);
		}

		function save() {
			const c = d.get_value("crop");
			const rows = (d.fields_dict.rows.df.data || [])
				.filter((r) => r.fertilizer || flt(r.rate))
				.map((r) => Object.fromEntries(TEMPLATE_FIELDS.map((f) => [f, r[f]])));
			if (!rows.length) {
				frappe.msgprint(__("Add at least one fertilizer row, or use Delete Template."));
				return;
			}
			frappe.call({
				method: TEMPLATE_API + "save_template",
				args: { crop: c, rows },
				freeze: true,
				freeze_message: __("Saving template…"),
			}).then((r) => {
				d.hide();
				frappe.show_alert({
					message: __("Template saved for {0} ({1} fertilizers)", [esc(c), (r.message.rows || []).length]),
					indicator: "green",
				});
				if (opts.on_save) opts.on_save(c);
			});
		}

		function remove() {
			farm_advisory.delete_template(d.get_value("crop"), (c) => {
				d.hide();
				if (opts.on_delete) opts.on_delete(c);
			});
		}

		d.show();
		await load(crop);
	};

	/** Delete a crop's template from a list, after confirmation (the server checks permission). */
	farm_advisory.delete_template = function (crop, on_delete) {
		const c = frappe.utils.escape_html(crop);
		frappe.confirm(__("Delete the fertilizer template of {0}? Saved recommendations keep their rows; Load Template will no longer find a template for {0}.", [c]), () => {
			frappe.call({ method: TEMPLATE_API + "delete_template", args: { crop }, freeze: true }).then(() => {
				frappe.show_alert({ message: __("Template of {0} deleted", [c]), indicator: "orange" });
				if (on_delete) on_delete(crop);
			});
		});
	};
})();
