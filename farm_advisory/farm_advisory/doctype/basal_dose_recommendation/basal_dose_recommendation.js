// Copyright (c) 2026, Uday Dange and contributors
//
// Fertilizer Basal Dose Recommendation form.
// All quantities, bags and costs come from farm_advisory.api.preview_basal_dose
// (the same Python as validate()); this script collects input only.

const BASAL_PF = "Basal Dose Recommendation Report";
// No html_field: the report is shown only through Print / PDF, never on the form.
const BASAL_PREVIEW = {
	method: "farm_advisory.api.preview_basal_dose",
	tables: ["crops", "fertilizers"],
	after(frm, msg) {
		sync_purchase_list(frm, msg);
		render_crop_cards(frm);
	},
};

function basal_recalc(frm) {
	farm_advisory.preview(frm, BASAL_PREVIEW);
}

function sync_purchase_list(frm, msg) {
	const key = (rows) => JSON.stringify((rows || []).map((p) =>
		[p.fertilizer_name, flt(p.pack_kg), flt(p.qty_kg, 6), flt(p.amount, 6)]));
	if (key(frm.doc.purchase_items) === key(msg.purchase_items)) return;
	frm.doc.purchase_items = [];
	(msg.purchase_items || []).forEach((p) => frm.add_child("purchase_items", p));
	frm.refresh_field("purchase_items");
}

function max_crop_no(frm) {
	return Math.max(0, ...(frm.doc.crops || []).map((c) => c.crop_no || 0));
}

function rows_of(frm, crop_no) {
	return (frm.doc.fertilizers || []).filter((r) => r.crop_no === crop_no);
}

/** Replace a crop's fertilizer rows with a crop template (``tplRows``). */
function load_template(frm, crop_no, template) {
	rows_of(frm, crop_no).forEach((r) => frappe.model.clear_doc(r.doctype, r.name));
	const rows = template.length ? template : [{ rate_unit: "gm / plant", pack_kg: 25 }];
	rows.forEach((t) => frm.add_child("fertilizers", { ...t, crop_no }));
	order_fertilizers(frm);
}

/** Keep each crop's fertilizer rows together, in crop order. */
function order_fertilizers(frm) {
	(frm.doc.fertilizers || []).sort((a, b) => (a.crop_no - b.crop_no) || (a.idx - b.idx));
	(frm.doc.fertilizers || []).forEach((r, i) => (r.idx = i + 1));
	frm.refresh_field("fertilizers");
	render_crop_cards(frm);
}

/** A crop was chosen on a row: default spacing, then its template (confirming a replace). */
function apply_crop(frm, row) {
	if (!row.crop) return basal_recalc(frm);
	frappe.call({
		method: "farm_advisory.api.get_crop_defaults",
		args: { crop: row.crop },
	}).then((r) => {
		const d = r.message || {};
		Object.assign(row, {
			row_spacing: d.row_spacing, plant_spacing: d.plant_spacing,
			spacing_unit: "Feet", plants_manual: 0, variety: "",
		});
		frm.refresh_field("crops");
		const has_rows = rows_of(frm, row.crop_no).some((x) => x.fertilizer || x.fertilizer_name);
		const replace = () => { load_template(frm, row.crop_no, d.template || []); basal_recalc(frm); };
		if (has_rows) {
			frappe.confirm(__("Replace fertilizer rows with the {0} template?", [row.crop]), replace,
				() => basal_recalc(frm));
		} else {
			replace();
		}
	});
}

function add_crop(frm, crop) {
	const row = frm.add_child("crops", {
		crop_no: max_crop_no(frm) + 1, crop, area: 1, area_unit: "Acre", spacing_unit: "Feet",
	});
	frm.refresh_field("crops");
	render_crop_cards(frm);
	apply_crop(frm, row);
}

function prompt_add_crop(frm) {
	frappe.prompt({
		fieldname: "crop", fieldtype: "Link", options: "Farm Crop", label: __("Crop"), reqd: 1,
		get_query: () => ({ filters: { used_in_basal: 1 } }),
		description: __("The crop gets its own section, plant count and fertilizer table."),
	}, (v) => add_crop(frm, v.crop), __("Add Crop"), __("Add Crop"));
}

// ── crop-wise editor ──────────────────────────────────────────────────
// One card per crop: its details, its own fertilizer rows and its subtotal,
// then the combined purchase summary and the recommendation total. The cards
// edit the same crops / fertilizers tables the server calculates; every figure
// they show was returned by the preview, never computed here.

const BASAL_CROP_DF = (f) => frappe.meta.get_docfield("Basal Dose Crop", f);
const BASAL_FERT_DF = (f) => frappe.meta.get_docfield("Basal Dose Fertilizer", f);
const cc_esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
const cc_num = (v, max = 2) =>
	Number(flt(v)).toLocaleString("en-IN", { maximumFractionDigits: max });
const cc_money = (v) => frappe.format(flt(v), { fieldtype: "Currency" });
const cc_label = (text) => `data-label="${cc_esc(text)}"`;

function crop_cards_editable(frm) {
	return frm.is_new() ? frappe.model.can_create(frm.doctype) : frm.has_perm("write");
}

function sorted_crops(frm) {
	return (frm.doc.crops || []).slice().sort((a, b) => (a.crop_no - b.crop_no) || (a.idx - b.idx));
}

function crop_title(c) {
	return c.crop || __("No crop selected");
}

/** "Mango - Kesar" (the variety's record name) shown as "Kesar" inside the Mango card. */
function variety_label(c) {
	if (!c.variety) return "—";
	const prefix = `${c.crop} - `;
	return c.variety.startsWith(prefix) ? c.variety.slice(prefix.length) : c.variety;
}

function render_crop_cards(frm) {
	const field = frm.get_field("crop_cards");
	if (!field || !field.$wrapper) return;
	frappe.dom.set_style(CROP_CARDS_CSS, "fa-crop-cards-style");
	const edit = crop_cards_editable(frm);
	const crops = sorted_crops(frm);
	const btn = (action, label, cls = "btn-default", data = "") =>
		`<button type="button" class="btn btn-xs ${cls}" data-action="${action}" ${data}>${label}</button>`;
	const add_crop_btn = edit
		? `<button type="button" class="btn btn-sm btn-primary" data-action="add-crop">
			${frappe.utils.icon("add", "xs")} ${__("Add Crop")}</button>` : "";

	if (!crops.length) {
		field.$wrapper.html(`<div class="fa-cc"><div class="fa-cc-empty">
			<div class="fa-cc-empty-title">${__("No crops added yet.")}</div>
			<div class="fa-cc-muted">${__("Add a crop to start this recommendation. Each crop gets its own fertilizer table.")}</div>
			${add_crop_btn}</div></div>`);
		bind_crop_cards(frm, field.$wrapper);
		return;
	}

	const cards = crops.map((c) => {
		const no = `data-crop-no="${c.crop_no}"`;
		const name = cc_esc(crop_title(c));
		const rows = rows_of(frm, c.crop_no);
		const plants = c.plants_manual ? __("{0} (entered)", [cc_num(c.plant_count, 0)])
			: __("{0} (from area and spacing)", [cc_num(c.plant_count, 0)]);
		const spacing = flt(c.row_spacing) && flt(c.plant_spacing)
			? `${cc_num(c.row_spacing, 4)} × ${cc_num(c.plant_spacing, 4)} ${cc_esc(__(c.spacing_unit || "Feet"))}` : "—";
		const details = [
			[__("Variety"), cc_esc(variety_label(c))],
			[__("Area"), `${cc_num(c.area, 4)} ${cc_esc(__(c.area_unit || "Acre"))}`],
			[__("Spacing (row × plant)"), spacing],
			[__("Plant Count"), plants],
			[__("Dose per Plant"), `${cc_num(c.dose_gm_per_plant)} gm`],
		];
		// data-label: the column name each cell shows when a narrow card stacks the row
		const body = rows.length ? rows.map((r, i) => `<tr>
			<td class="fa-cc-n">${i + 1}</td>
			<td class="fa-cc-wide">${r.fertilizer_name || r.fertilizer
				? `<div class="fa-cc-strong">${cc_esc(r.fertilizer_name || r.fertilizer)}</div>`
				: `<div class="fa-cc-muted">${__("No fertilizer chosen")}</div>`}
				${r.contains ? `<div class="fa-cc-muted">${cc_esc(r.contains)}</div>` : ""}</td>
			<td class="r" ${cc_label(__("Rate"))}>${cc_num(r.rate, 4)}</td>
			<td class="nowrap" ${cc_label(__("Unit"))}>${cc_esc(__(r.rate_unit || "gm / plant"))}</td>
			<td class="r" ${cc_label(__("Quantity (kg)"))}>${cc_num(r.qty_kg, 3)}</td>
			<td class="r" ${cc_label(__("Pack (kg)"))}>${cc_num(r.pack_kg)}</td>
			<td class="r" ${cc_label(__("Bags"))}>${cc_num(r.bags)}</td>
			<td class="r nowrap" ${cc_label(__("Cost / Bag"))}>${cc_money(r.cost_per_bag)}</td>
			<td class="r nowrap fa-cc-strong" ${cc_label(__("Amount"))}>${cc_money(r.amount)}</td>
			${edit ? `<td class="nowrap fa-cc-wide"><div class="fa-cc-row-actions">
				${btn("edit-fert", __("Edit"), "btn-default", `data-row="${cc_esc(r.name)}"`)}
				${btn("delete-fert", __("Delete"), "btn-default", `data-row="${cc_esc(r.name)}"`)}</div></td>` : ""}
		</tr>`).join("") : `<tr><td colspan="${edit ? 10 : 9}" class="fa-cc-none">
			${__("No fertilizer rows for {0} yet.", [name])}
			${edit ? __("Use Add Fertilizer or Load Template.") : ""}</td></tr>`;

		return `<section class="fa-cc-card" ${no} aria-label="${name}">
			<header class="fa-cc-head">
				<div class="fa-cc-heading">
					<span class="fa-cc-badge">${__("Crop {0}", [c.crop_no])}</span>
					<h4>${__("{0} — Crop Recommendation", [name])}</h4>
				</div>
				${edit ? `<div class="fa-cc-actions">
					${btn("edit-crop", __("Edit Crop"), "btn-default", no)}
					${btn("template", __("Load Template"), "btn-default", no)}
					${btn("remove-crop", __("Remove Crop"), "btn-default fa-cc-danger", no)}</div>` : ""}
			</header>
			<dl class="fa-cc-details">${details.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>
			<div class="fa-cc-table-wrap"><table class="fa-cc-table">
				<caption class="sr-only">${__("{0} fertilizer recommendations", [name])}</caption>
				<thead><tr><th>#</th><th>${__("Fertilizer")}</th><th class="r">${__("Rate")}</th><th>${__("Unit")}</th>
					<th class="r">${__("Quantity (kg)")}</th><th class="r">${__("Pack (kg)")}</th><th class="r">${__("Bags")}</th>
					<th class="r">${__("Cost / Bag")}</th><th class="r">${__("Amount")}</th>${edit ? "<th></th>" : ""}</tr></thead>
				<tbody>${body}</tbody>
				<tfoot><tr class="fa-cc-subtotal">
					<td></td><td class="fa-cc-wide">${__("{0} Subtotal", [name])}</td><td></td><td></td>
					<td class="r" ${cc_label(__("Quantity (kg)"))}>${cc_num(c.total_qty_kg, 3)}</td><td></td>
					<td class="r" ${cc_label(__("Bags"))}>${cc_num(c.total_bags)}</td>
					<td class="r fa-cc-muted nowrap" ${cc_label(__("Per Plant"))}>${cc_money(c.cost_per_plant)}</td>
					<td class="r nowrap" ${cc_label(__("Amount"))}>${cc_money(c.total_cost)}</td>${edit ? "<td></td>" : ""}</tr></tfoot>
			</table></div>
			${edit ? `<div class="fa-cc-foot">${btn("add-fert",
				`${frappe.utils.icon("add", "xs")} ${__("Add Fertilizer to {0}", [name])}`, "btn-default", no)}</div>` : ""}
		</section>`;
	}).join("");

	// which crops use each purchase line (display only; the quantities are the server's)
	const used_by = {};
	(frm.doc.fertilizers || []).forEach((r) => {
		const c = crops.find((x) => x.crop_no === r.crop_no);
		const key = `${r.fertilizer_name}|${flt(r.pack_kg)}`;
		if (c && r.fertilizer_name) (used_by[key] = used_by[key] || new Set()).add(crop_title(c));
	});
	const purchase = frm.doc.purchase_items || [];
	const purchase_html = purchase.length ? `<section class="fa-cc-block">
		<h4>${__("Combined Fertilizer Purchase Summary")}</h4>
		<p class="fa-cc-muted">${__("The same fertilizer and pack size added up across all crops, for purchasing. These amounts are already in the crop subtotals and are not added to the total again.")}</p>
		<div class="fa-cc-table-wrap"><table class="fa-cc-table">
			<thead><tr><th>${__("Fertilizer")}</th><th>${__("Used For")}</th><th class="r">${__("Pack (kg)")}</th>
				<th class="r">${__("Total Quantity (kg)")}</th><th class="r">${__("Amount (sum of crop-wise)")}</th></tr></thead>
			<tbody>${purchase.map((p) => `<tr><td class="fa-cc-strong fa-cc-wide">${cc_esc(p.fertilizer_name)}</td>
				<td class="fa-cc-wide" ${cc_label(__("Used For"))}>
					${cc_esc([...(used_by[`${p.fertilizer_name}|${flt(p.pack_kg)}`] || [])].join(", "))}</td>
				<td class="r" ${cc_label(__("Pack (kg)"))}>${cc_num(p.pack_kg)}</td>
				<td class="r" ${cc_label(__("Total Quantity (kg)"))}>${cc_num(p.qty_kg, 3)}</td>
				<td class="r nowrap" ${cc_label(__("Amount"))}>${cc_money(p.amount)}</td></tr>`).join("")}</tbody>
		</table></div></section>` : "";

	const total_html = `<section class="fa-cc-block fa-cc-total">
		<h4>${__("Total Recommendation Cost")}</h4>
		<table class="fa-cc-sum"><tbody>
			${crops.map((c) => `<tr><td>${__("Crop {0} — {1} subtotal", [c.crop_no, cc_esc(crop_title(c))])}</td>
				<td class="r nowrap">${cc_money(c.total_cost)}</td></tr>`).join("")}
			<tr class="fa-cc-grand"><td>${crops.length === 1 ? __("Total (1 crop)") : __("Total ({0} crops)", [crops.length])}</td>
			<td class="r nowrap">${cc_money(frm.doc.grand_total)}</td></tr></tbody></table>
		<div class="fa-cc-muted">${__("{0} plants · {1} kg fertilizer in total", [
			cc_num(frm.doc.total_plants, 0), cc_num(frm.doc.total_qty_kg, 3)])}</div>
	</section>`;

	field.$wrapper.html(`<div class="fa-cc">${cards}
		${add_crop_btn ? `<div class="fa-cc-add">${add_crop_btn}</div>` : ""}
		${purchase_html}${total_html}</div>`);
	bind_crop_cards(frm, field.$wrapper);
}

function bind_crop_cards(frm, $wrapper) {
	$wrapper.off(".facc").on("click.facc", "[data-action]", (e) => {
		const $b = $(e.currentTarget);
		const crop = (frm.doc.crops || []).find((c) => c.crop_no === cint($b.attr("data-crop-no")));
		const row = (frm.doc.fertilizers || []).find((r) => r.name === $b.attr("data-row"));
		({
			"add-crop": () => prompt_add_crop(frm),
			"edit-crop": () => crop && crop_dialog(frm, crop),
			"template": () => crop && load_crop_template(frm, crop),
			"remove-crop": () => crop && remove_crop(frm, crop),
			"add-fert": () => crop && fertilizer_dialog(frm, crop, null),
			"edit-fert": () => row && fertilizer_dialog(frm, crop_of(frm, row), row),
			"delete-fert": () => row && delete_fertilizer(frm, row),
		})[$b.attr("data-action")]();
	});
}

function crop_of(frm, row) {
	return (frm.doc.crops || []).find((c) => c.crop_no === row.crop_no) || {};
}

function select_options(field) {
	return (field && field.options) || "";
}

function crop_dialog(frm, c) {
	const d = new frappe.ui.Dialog({
		title: __("Crop {0} — {1}", [c.crop_no, crop_title(c)]),
		fields: [
			{ fieldname: "crop", fieldtype: "Link", options: "Farm Crop", label: __("Crop"), reqd: 1,
			  default: c.crop, get_query: () => ({ filters: { used_in_basal: 1 } }),
			  description: __("Changing the crop reloads its default spacing and fertilizer template.") },
			{ fieldname: "variety", fieldtype: "Link", options: "Farm Crop Variety", label: __("Variety"),
			  default: c.variety,
			  get_query: () => ({ filters: { crop: d.get_value("crop") || "", used_in_basal: 1 } }) },
			{ fieldtype: "Section Break", label: __("Area") },
			{ fieldname: "area", fieldtype: "Float", label: __("Area"), default: c.area, non_negative: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "area_unit", fieldtype: "Select", label: __("Area Unit"),
			  options: select_options(BASAL_CROP_DF("area_unit")), default: c.area_unit },
			{ fieldtype: "Section Break", label: __("Spacing") },
			{ fieldname: "row_spacing", fieldtype: "Float", label: __("Row Spacing"), default: c.row_spacing, non_negative: 1 },
			{ fieldname: "plant_spacing", fieldtype: "Float", label: __("Plant Spacing"), default: c.plant_spacing,
			  non_negative: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "spacing_unit", fieldtype: "Select", label: __("Spacing Unit"),
			  options: select_options(BASAL_CROP_DF("spacing_unit")), default: c.spacing_unit },
			{ fieldtype: "Section Break", label: __("Plants") },
			{ fieldname: "plants_manual", fieldtype: "Check", label: __("Enter the plant count manually"),
			  default: c.plants_manual },
			{ fieldname: "plant_count", fieldtype: "Int", label: __("Plant Count"), default: c.plant_count,
			  depends_on: "eval:doc.plants_manual", non_negative: 1,
			  description: __("Otherwise it is calculated from the area and spacing.") },
		],
		primary_action_label: __("Apply"),
		primary_action(v) {
			d.hide();
			if (v.crop !== c.crop) {
				// a new crop starts from its own defaults and template, as when it was first added
				c.crop = v.crop;
				frm.dirty();
				apply_crop(frm, c);
				return;
			}
			Object.assign(c, {
				variety: v.variety || "", area: flt(v.area), area_unit: v.area_unit,
				row_spacing: flt(v.row_spacing), plant_spacing: flt(v.plant_spacing), spacing_unit: v.spacing_unit,
				plants_manual: cint(v.plants_manual),
			});
			if (c.plants_manual) c.plant_count = cint(v.plant_count);
			changed(frm, "crops");
		},
	});
	d.show();
}

function fertilizer_dialog(frm, c, row) {
	const r = row || { rate_unit: "gm / plant" };
	let name = r.fertilizer_name;
	const d = new frappe.ui.Dialog({
		title: row ? __("Edit Fertilizer — {0}", [crop_title(c)]) : __("Add Fertilizer to {0}", [crop_title(c)]),
		fields: [
			{ fieldname: "fertilizer", fieldtype: "Link", options: "Farm Fertilizer", label: __("Fertilizer"),
			  reqd: !r.fertilizer_name, default: r.fertilizer, get_query: () => ({ filters: { is_active: 1 } }),
			  onchange() {
				const f = d.get_value("fertilizer");
				if (!f || f === r.fertilizer) return;
				// a newly chosen fertilizer fills its master values; all stay editable
				frappe.db.get_value("Farm Fertilizer", f, ["fertilizer_name", "pack_kg", "contains", "cost_per_bag"])
					.then((res) => {
						const m = res.message || {};
						name = m.fertilizer_name;
						d.set_values({ pack_kg: m.pack_kg, contains: m.contains, cost_per_bag: m.cost_per_bag });
					});
			  } },
			{ fieldname: "contains", fieldtype: "Data", label: __("Contains"), default: r.contains },
			{ fieldtype: "Section Break" },
			{ fieldname: "rate", fieldtype: "Float", label: __("Rate"), default: r.rate, non_negative: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "rate_unit", fieldtype: "Select", label: __("Unit"),
			  options: select_options(BASAL_FERT_DF("rate_unit")), default: r.rate_unit },
			{ fieldtype: "Section Break" },
			{ fieldname: "pack_kg", fieldtype: "Float", label: __("Pack (kg)"), default: r.pack_kg, non_negative: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "cost_per_bag", fieldtype: "Currency", label: __("Cost / Bag"), default: r.cost_per_bag,
			  non_negative: 1 },
		],
		primary_action_label: row ? __("Apply") : __("Add"),
		primary_action(v) {
			d.hide();
			const values = {
				fertilizer: v.fertilizer || "", fertilizer_name: name || v.fertilizer || "",
				contains: v.contains || "", rate: flt(v.rate), rate_unit: v.rate_unit,
				pack_kg: flt(v.pack_kg), cost_per_bag: flt(v.cost_per_bag),
			};
			if (row) {
				Object.assign(row, values);
				changed(frm, "fertilizers");
			} else {
				frm.add_child("fertilizers", { ...values, crop_no: c.crop_no });
				order_fertilizers(frm);
				changed(frm, "fertilizers");
			}
		},
	});
	d.show();
}

function delete_fertilizer(frm, row) {
	const c = crop_of(frm, row);
	frappe.confirm(__("Delete {0} from {1}? Other crops are not changed.",
		[cc_esc(row.fertilizer_name || row.fertilizer || __("this row")), cc_esc(crop_title(c))]), () => {
		frappe.model.clear_doc(row.doctype, row.name);
		order_fertilizers(frm);
		changed(frm, "fertilizers");
	});
}

function remove_crop(frm, c) {
	const rows = rows_of(frm, c.crop_no);
	frappe.confirm(__("Remove {0} (crop {1}) and its {2} fertilizer row(s)? Other crops are not changed.",
		[cc_esc(crop_title(c)), c.crop_no, rows.length]), () => {
		// the crop's own rows go with it, so none is left to attach to another crop
		rows.forEach((r) => frappe.model.clear_doc(r.doctype, r.name));
		frappe.model.clear_doc(c.doctype, c.name);
		frm.refresh_field("crops");
		order_fertilizers(frm);
		changed(frm, "crops");
	});
}

function load_crop_template(frm, c) {
	if (!c.crop) return frappe.msgprint(__("Choose the crop first."));
	load_template_into(frm, c.crop_no, c.crop);
}

/**
 * Load the template of ``template_crop`` into crop ``crop_no``. Rows the user
 * entered are only replaced after a confirmation; a crop without a template
 * offers to create one (the server decides who may) and then loads it.
 */
function load_template_into(frm, crop_no, template_crop) {
	frappe.call({ method: "farm_advisory.api.get_crop_defaults", args: { crop: template_crop } }).then((r) => {
		const tpl = (r.message || {}).template || [];
		if (!tpl.length) return no_template(frm, crop_no, template_crop);
		const target = (frm.doc.crops || []).find((x) => x.crop_no === crop_no) || {};
		const entered = rows_of(frm, crop_no).filter((x) => x.fertilizer || x.fertilizer_name);
		const load = () => {
			load_template(frm, crop_no, tpl);
			changed(frm, "fertilizers");
			frappe.show_alert({ message: __("{0} template loaded into {1} (crop {2})",
				[cc_esc(template_crop), cc_esc(crop_title(target)), crop_no]), indicator: "green" });
		};
		if (!entered.length) return load();
		frappe.confirm(__("Replace the {0} fertilizer row(s) of {1} (crop {2}) with the {3} template ({4} rows)?",
			[entered.length, cc_esc(crop_title(target)), crop_no, cc_esc(template_crop), tpl.length]), load);
	});
}

function no_template(frm, crop_no, template_crop) {
	const name = cc_esc(template_crop);
	// a hint for which button to show; saving a template is checked again on the server
	const can_create = frappe.model.can_write("Farm Crop");
	const d = new frappe.ui.Dialog({
		title: __("No Template for {0}", [name]),
		fields: [{ fieldtype: "HTML", options: `<p>${__("{0} has no fertilizer template yet.", [name])}</p>
			<p class="text-muted">${can_create
				? __("Create one from the approved fertilizer schedule and it loads into this crop, or close this and add fertilizers manually.")
				: __("Ask a Farm Advisory Manager to add one on the Basal Dose page, or add fertilizers manually.")}</p>` }],
		primary_action_label: can_create ? __("Create Template") : __("Close"),
		primary_action() {
			d.hide();
			if (!can_create) return;
			farm_advisory.template_editor(template_crop, {
				on_save: () => load_template_into(frm, crop_no, template_crop),
			});
		},
	});
	d.show();
}

/** A card edited the document: mark it, redraw, and ask the server for the new figures. */
function changed(frm, table) {
	frm.refresh_field(table);
	frm.dirty();
	render_crop_cards(frm);
	basal_recalc(frm);
}

const CROP_CARDS_CSS = `
.fa-cc { --fa-cc-accent: var(--green-600, #2f7a4b); --fa-cc-soft: var(--green-50, #eef7f1);
	display: flex; flex-direction: column; gap: 16px; }
.fa-cc .r { text-align: right; }
.fa-cc .nowrap { white-space: nowrap; }
.fa-cc-muted { color: var(--text-muted); font-size: var(--text-sm, 12px); }
.fa-cc-strong { font-weight: 600; color: var(--heading-color, var(--text-color)); }
.fa-cc-card, .fa-cc-block, .fa-cc-empty { border: 1px solid var(--border-color); border-radius: var(--border-radius-md, 8px);
	background: var(--card-bg, var(--fg-color)); overflow: hidden; }
.fa-cc-card { border-left: 3px solid var(--fa-cc-accent); }
.fa-cc-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px 16px;
	padding: 10px 16px; background: var(--subtle-fg, var(--control-bg)); border-bottom: 1px solid var(--border-color); }
.fa-cc-heading { display: flex; align-items: center; gap: 10px; min-width: 0; }
.fa-cc-heading h4, .fa-cc-block h4 { margin: 0; font-size: var(--text-lg, 16px); font-weight: 600;
	color: var(--heading-color, var(--text-color)); }
.fa-cc-badge { flex: 0 0 auto; padding: 2px 8px; border-radius: 999px; background: var(--fa-cc-soft);
	color: var(--fa-cc-accent); font-size: var(--text-xs, 11px); font-weight: 600; }
.fa-cc-actions { display: flex; flex-wrap: wrap; gap: 6px; }
.fa-cc-row-actions { display: flex; flex-wrap: nowrap; gap: 4px; }
.fa-cc-row-actions { justify-content: flex-end; }
.fa-cc-danger { color: var(--red-600, #c0392b) !important; }
.fa-cc-details { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px 16px;
	margin: 0; padding: 12px 16px; border-bottom: 1px solid var(--border-color); }
.fa-cc-details dt { color: var(--text-muted); font-size: var(--text-xs, 11px); font-weight: 500; }
.fa-cc-details dd { margin: 2px 0 0; color: var(--heading-color, var(--text-color)); font-weight: 500; }
.fa-cc-table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
.fa-cc-table, .fa-cc-sum { width: 100%; margin: 0; border-collapse: collapse; font-size: var(--text-sm, 13px); }
.fa-cc-table th { padding: 8px 10px; background: var(--subtle-fg, var(--control-bg)); color: var(--text-muted);
	font-size: var(--text-xs, 12px); font-weight: 600; white-space: nowrap; text-align: left;
	border-bottom: 1px solid var(--border-color); }
.fa-cc-table th.r { text-align: right; }
.fa-cc-table td { padding: 8px 10px; border-bottom: 1px solid var(--border-color); vertical-align: top; }
.fa-cc-table th:first-child, .fa-cc-table td:first-child { padding-left: 16px; }
.fa-cc-table th:last-child, .fa-cc-table td:last-child { padding-right: 16px; }
.fa-cc-n { color: var(--text-muted); width: 1%; }
.fa-cc-none { color: var(--text-muted); text-align: center; padding: 16px !important; }
.fa-cc-subtotal td { background: var(--fa-cc-soft); color: var(--heading-color, var(--text-color)); font-weight: 600;
	border-bottom: 0; border-top: 2px solid var(--fa-cc-accent); }
.fa-cc-foot { padding: 10px 16px; border-top: 1px solid var(--border-color); }
.fa-cc-add { display: flex; justify-content: flex-start; }
.fa-cc-block { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
.fa-cc-block p { margin: 0; }
.fa-cc-block .fa-cc-table-wrap { margin: 0 -16px; border-top: 1px solid var(--border-color); }
.fa-cc-block .fa-cc-table tbody tr:last-child td { border-bottom: 0; }
.fa-cc-total { border-left: 3px solid var(--fa-cc-accent); }
.fa-cc-sum td { padding: 6px 0; border-bottom: 1px solid var(--border-color); }
.fa-cc-sum .fa-cc-grand td { border-bottom: 0; padding-top: 10px; font-size: var(--text-lg, 16px); font-weight: 700;
	color: var(--heading-color, var(--text-color)); }
.fa-cc-empty { padding: 28px 16px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.fa-cc-empty-title { font-weight: 600; color: var(--heading-color, var(--text-color)); }
/* a narrow form stacks every table row into a labelled card, so no column is off-screen */
.fa-cc { container: fa-cc / inline-size; }
@container fa-cc (max-width: 639px) {
	.fa-cc-table thead { display: none; }
	.fa-cc-table, .fa-cc-table tbody, .fa-cc-table tfoot { display: block; width: 100%; }
	.fa-cc-table tr { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 12px;
		padding: 10px 12px; border-bottom: 1px solid var(--border-color); }
	.fa-cc-table td, .fa-cc-table td.r, .fa-cc-table td:first-child, .fa-cc-table td:last-child {
		display: block; padding: 0; border: 0; text-align: left; white-space: normal; background: none; }
	.fa-cc-table td.fa-cc-n, .fa-cc-table td:empty { display: none; }
	.fa-cc-table td.fa-cc-wide, .fa-cc-table td.fa-cc-none { grid-column: 1 / -1; }
	.fa-cc-table td[data-label]::before { content: attr(data-label); display: block; color: var(--text-muted);
		font-size: var(--text-xs, 11px); font-weight: 500; }
	.fa-cc-table .fa-cc-row-actions { justify-content: flex-start; }
	.fa-cc-table tr.fa-cc-subtotal { background: var(--fa-cc-soft); border-top: 2px solid var(--fa-cc-accent);
		border-bottom: 0; font-weight: 600; }
	.fa-cc-block .fa-cc-table-wrap { overflow: visible; }
}
@media (max-width: 575px) {
	.fa-cc-head, .fa-cc-details, .fa-cc-foot, .fa-cc-block { padding-left: 12px; padding-right: 12px; }
	.fa-cc-block .fa-cc-table-wrap { margin: 0 -12px; }
	.fa-cc-heading h4, .fa-cc-block h4 { font-size: var(--text-md, 14px); }
	.fa-cc-details { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}`;

function crop_rows_options(frm) {
	return (frm.doc.crops || []).map((c) => ({
		value: String(c.crop_no), label: `${c.crop_no}. ${c.crop || __("(no crop)")}`,
	}));
}

frappe.ui.form.on("Basal Dose Recommendation", {
	setup(frm) {
		frm.set_query("crop", "crops", () => ({ filters: { used_in_basal: 1 } }));
		frm.set_query("variety", "crops", (doc, cdt, cdn) => ({
			filters: { crop: locals[cdt][cdn].crop || "", used_in_basal: 1 },
		}));
		frm.set_query("fertilizer", "fertilizers", () => ({ filters: { is_active: 1 } }));
	},

	onload(frm) {
		if (!frm.is_new()) return;
		frappe.db.get_single_value("Farm Advisory Settings", "default_bag_rounding").then((v) => {
			if (v && frm.doc.bag_rounding !== v) frm.set_value("bag_rounding", v);
		});
		// the prototype opens with a Mango crop and its template; the Basal Dose
		// page's crop tabs open a new record with their own crop instead
		const start_crop = farm_advisory.basal_start_crop || "Mango";
		farm_advisory.basal_start_crop = null;
		if (!(frm.doc.crops || []).length) add_crop(frm, start_crop);
	},

	refresh(frm) {
		render_crop_cards(frm);
		basal_recalc(frm);

		frm.add_custom_button(__("Add Crop"), () => prompt_add_crop(frm));
		frm.add_custom_button(__("Load Template"), () => frm.trigger("load_template_dialog"));
		if (!frm.doc.customer) {
			frm.add_custom_button(__("Create Customer"), () => farm_advisory.create_customer(frm));
		}
		if (frm.is_new()) {
			frm.add_custom_button(__("Import Old Calculator File"), () => frm.trigger("import_legacy"));
		}
		frm.add_custom_button(__("Print / PDF"), () => farm_advisory.print(frm, BASAL_PF), __("Report"));
		frm.add_custom_button(__("Download PDF"), () => farm_advisory.download_pdf(frm, BASAL_PF), __("Report"));
		frm.add_custom_button(__("Excel / CSV"), async () => {
			if (!(await farm_advisory.ensure_saved(frm))) return;
			window.open("/api/method/farm_advisory.api.download_basal_csv?name=" +
				encodeURIComponent(frm.doc.name));
		}, __("Report"));
		frm.add_custom_button(__("WhatsApp"), () => farm_advisory.share_whatsapp(frm, BASAL_PF), __("Report"));
	},

	load_template_dialog(frm) {
		if (!(frm.doc.crops || []).length) {
			frappe.msgprint(__("Add a crop first."));
			return;
		}
		const options = crop_rows_options(frm);
		const d = new frappe.ui.Dialog({
			title: __("Load Template"),
			fields: [
				{ fieldname: "crop_no", fieldtype: "Select", label: __("Into crop"), options,
				  default: options[options.length - 1].value, reqd: 1 },
				{ fieldname: "template", fieldtype: "Link", options: "Farm Crop", label: __("Template of"),
				  reqd: 1, get_query: () => ({ filters: { used_in_basal: 1 } }) },
			],
			primary_action_label: __("Load"),
			primary_action(v) {
				d.hide();
				load_template_into(frm, cint(v.crop_no), v.template);
			},
		});
		const crop_no = cint(d.get_value("crop_no"));
		const row = (frm.doc.crops || []).find((c) => c.crop_no === crop_no);
		if (row && row.crop) d.set_value("template", row.crop);
		d.show();
	},

	import_legacy(frm) {
		const input = document.createElement("input");
		input.type = "file";
		input.accept = ".json,application/json";
		input.onchange = () => {
			const file = input.files[0];
			if (!file) return;
			const reader = new FileReader();
			reader.onload = () => {
				frappe.call({
					method: "farm_advisory.api.import_legacy_basal_file",
					args: { content: reader.result },
					freeze: true,
				}).then((r) => {
					const v = r.message || {};
					const { crops, fertilizers, ...fields } = v;
					frm.clear_table("crops");
					frm.clear_table("fertilizers");
					(crops || []).forEach((c) => frm.add_child("crops", c));
					(fertilizers || []).forEach((f) => frm.add_child("fertilizers", f));
					Object.keys(fields).forEach((k) => (frm.doc[k] = fields[k]));
					frm.refresh_fields();
					frm.dirty();
					basal_recalc(frm);
					frappe.msgprint(__("Imported. Select or create the farmer's Customer, check the values and save."));
				});
			};
			reader.readAsText(file);
		};
		input.click();
	},

	customer(frm) { farm_advisory.fill_from_customer(frm); },
	mobile_no(frm) { farm_advisory.sync_whatsapp(frm); },
	whatsapp_same_as_mobile(frm) { farm_advisory.sync_whatsapp(frm); },
	bag_rounding: basal_recalc,
	first_name: basal_recalc,
	middle_name: basal_recalc,
	last_name: basal_recalc,
	village: basal_recalc,
	taluka: basal_recalc,
	district: basal_recalc,
	state: basal_recalc,
	pin_code: basal_recalc,

	crops_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.crop_no) row.crop_no = max_crop_no(frm) + 1;
		frm.refresh_field("crops");
	},
	crops_remove(frm) {
		const live = new Set((frm.doc.crops || []).map((c) => c.crop_no));
		const orphans = (frm.doc.fertilizers || []).filter((r) => !live.has(r.crop_no));
		if (orphans.length) {
			orphans.forEach((r) => frappe.model.clear_doc(r.doctype, r.name));
			frm.refresh_field("fertilizers");
			frappe.show_alert({ message: __("{0} fertilizer row(s) of the removed crop were removed",
				[orphans.length]), indicator: "orange" });
		}
		basal_recalc(frm);
	},
	fertilizers_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.crop_no) row.crop_no = max_crop_no(frm) || 1;
		frm.refresh_field("fertilizers");
	},
	fertilizers_remove: basal_recalc,
});

frappe.ui.form.on("Basal Dose Crop", {
	crop(frm, cdt, cdn) { apply_crop(frm, locals[cdt][cdn]); },
	variety: basal_recalc,
	row_spacing: basal_recalc,
	plant_spacing: basal_recalc,
	spacing_unit: basal_recalc,
	area: basal_recalc,
	area_unit: basal_recalc,
	plant_count(frm, cdt, cdn) {
		// typed by a person (the preview writes silently) → manual, as in the prototype
		const row = locals[cdt][cdn];
		if (!row.plants_manual) frappe.model.set_value(cdt, cdn, "plants_manual", 1);
		basal_recalc(frm);
	},
	plants_manual: basal_recalc,
});

frappe.ui.form.on("Basal Dose Fertilizer", {
	fertilizer(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.fertilizer) return basal_recalc(frm);
		frappe.db.get_value("Farm Fertilizer", row.fertilizer,
			["fertilizer_name", "pack_kg", "contains", "cost_per_bag"]).then((r) => {
			const f = r.message || {};
			// selecting a fertilizer fills its master values (still editable on the row)
			Object.assign(row, {
				fertilizer_name: f.fertilizer_name, pack_kg: f.pack_kg, contains: f.contains,
				cost_per_bag: f.cost_per_bag,
			});
			frm.refresh_field("fertilizers");
			basal_recalc(frm);
		});
	},
	crop_no: basal_recalc,
	pack_kg: basal_recalc,
	rate: basal_recalc,
	rate_unit: basal_recalc,
	cost_per_bag: basal_recalc,
});
