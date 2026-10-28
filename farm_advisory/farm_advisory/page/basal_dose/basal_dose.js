// Copyright (c) 2026, Uday Dange and contributors
//
// Basal Dose page: summary figures, one tab per crop listing the saved
// Basal Dose Recommendations that contain it, recent records and the
// fertilizer requirement. Read-only; the figures come from basal_dose.py,
// which limits them to records the user may read.

const BD_DOCTYPE = "Basal Dose Recommendation";
const BD_METHOD = "farm_advisory.farm_advisory.page.basal_dose.basal_dose.";
const BD_TEMPLATES = "farm_advisory.farm_advisory.doctype.farm_crop.farm_crop.get_template_overview";
const BD_PAGE_LENGTH = 20;
const BD_TAB_KEY = "farm_advisory.basal_dose.tab";

frappe.pages["basal-dose"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Basal Dose"),
		single_column: true,
	});
	wrapper.basal_dose = new BasalDosePage(page);
};

frappe.pages["basal-dose"].on_page_show = function (wrapper) {
	// a workspace link may open a given crop's tab: route_options = { crop }
	const crop = frappe.route_options && frappe.route_options.crop;
	frappe.route_options = null;
	wrapper.basal_dose.show(crop);
};

class BasalDosePage {
	constructor(page) {
		this.page = page;
		this.filters = { search: "", from_date: null, to_date: null, village: null };
		this.start = 0;
		this.list_seq = 0;
		this.setup_actions();
		this.make_layout();
		this.make_filters();
	}

	setup_actions() {
		this.page.set_primary_action(__("New Recommendation"), () => this.new_recommendation(), "add");
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.add_inner_button(__("All Recommendations"), () => frappe.set_route("List", BD_DOCTYPE));
		this.page.add_inner_button(__("Basal Dose Register"),
			() => this.open_report("Basal Dose Register"), __("Reports"));
		this.page.add_inner_button(__("Fertilizer Requirement Summary"),
			() => this.open_report("Fertilizer Requirement Summary"), __("Reports"));
	}

	make_layout() {
		// .fa-bd-shell is the size container the stylesheet's @container rules measure
		this.$main = $(`
			<div class="fa-bd-shell"><div class="fa-bd-page">
				<div class="fa-kpis" aria-label="${__("Summary")}"></div>

				<section class="fa-panel fa-crops">
					<div class="fa-tabs" role="tablist" aria-label="${__("Crop")}"></div>
					<div class="fa-toolbar">
						<div class="fa-filters"></div>
						<div class="fa-resultbar">
							<div class="fa-result-info" aria-live="polite"></div>
							<div class="fa-toolbar-actions">
								<button type="button" class="btn btn-default btn-sm fa-report">${__("Open Report")}</button>
								<button type="button" class="btn btn-default btn-sm fa-new"></button>
							</div>
						</div>
					</div>
					<div class="fa-list" id="fa-crop-panel" role="tabpanel"></div>
					<div class="fa-pager"></div>
				</section>

				<div class="fa-bottom">
					<section class="fa-panel">
						<header class="fa-panel-head">
							<div>
								<h2 class="fa-panel-title">${__("Recent Recommendations")}</h2>
								<div class="fa-panel-sub">${__("Latest saved records, all crops")}</div>
							</div>
							<button type="button" class="btn btn-link btn-xs fa-all">${__("View All")}</button>
						</header>
						<div class="fa-recent"></div>
					</section>
					<section class="fa-panel">
						<header class="fa-panel-head">
							<div>
								<h2 class="fa-panel-title">${__("Fertilizer Requirement")}</h2>
								<div class="fa-panel-sub">${__("Top items by quantity, all records")}</div>
							</div>
							<button type="button" class="btn btn-link btn-xs fa-fert-report">${__("Open Report")}</button>
						</header>
						<div class="fa-fert"></div>
					</section>
				</div>

				<section class="fa-panel fa-templates" id="fa-templates">
					<header class="fa-panel-head">
						<div>
							<h2 class="fa-panel-title">${__("Fertilizer Templates")}</h2>
							<div class="fa-panel-sub">${__("One template per crop. Load Template on a recommendation copies these rows into that crop's section.")}</div>
						</div>
						<button type="button" class="btn btn-primary btn-sm fa-tpl-add hidden">
							${frappe.utils.icon("add", "xs")}<span>${__("Add Template")}</span></button>
					</header>
					<div class="fa-tpl-toolbar">
						<input type="search" class="form-control input-sm fa-tpl-search"
							placeholder="${__("Search crop or fertilizer")}" aria-label="${__("Search crop or fertilizer")}">
						<select class="form-control input-sm fa-tpl-filter" aria-label="${__("Template status")}">
							<option value="">${__("All crops")}</option>
							<option value="with">${__("With template")}</option>
							<option value="without">${__("Without template")}</option>
						</select>
					</div>
					<div class="fa-tpl-list"></div>
				</section>
			</div></div>`).appendTo(this.page.main);

		this.$main.on("click", ".fa-tpl-add", () => this.edit_template(null));
		this.$main.on("click", ".fa-tpl-edit", (e) => this.edit_template($(e.currentTarget).attr("data-crop")));
		this.$main.on("click", ".fa-tpl-delete", (e) => farm_advisory.delete_template(
			$(e.currentTarget).attr("data-crop"), () => this.refresh()));
		this.$main.on("input change", ".fa-tpl-search, .fa-tpl-filter", () => this.render_templates());

		this.$main.on("click", ".fa-tab", (e) => this.select_crop($(e.currentTarget).attr("data-crop")));
		this.$main.on("keydown", ".fa-tab", (e) => this.tab_keydown(e));
		this.$main.on("click", ".fa-new, .fa-empty-new", () => this.new_recommendation());
		this.$main.on("click", ".fa-clear", () => this.clear_filters());
		this.$main.on("click", ".fa-report", () =>
			this.open_report("Basal Dose Register", { crop: this.crop }));
		this.$main.on("click", ".fa-fert-report", () => this.open_report("Fertilizer Requirement Summary"));
		this.$main.on("click", ".fa-all", () => frappe.set_route("List", BD_DOCTYPE));
		this.$main.on("click", ".fa-prev", () => this.page_to(this.start - BD_PAGE_LENGTH));
		this.$main.on("click", ".fa-next", () => this.page_to(this.start + BD_PAGE_LENGTH));
	}

	make_filters() {
		const $filters = this.$main.find(".fa-filters");
		const make = (df) => {
			const control = frappe.ui.form.make_control({
				parent: $(`<div class="fa-filter fa-filter-${df.fieldname}"></div>`).appendTo($filters),
				df: { ...df, change: () => this.set_filter(df.fieldname, control.get_value()) },
				render_input: true,
			});
			control.refresh();
			control.$input.attr("aria-label", df.placeholder);
			return control;
		};
		this.controls = {
			search: make({ fieldname: "search", fieldtype: "Data",
				placeholder: __("Search farmer, mobile, ID or customer") }),
			from_date: make({ fieldname: "from_date", fieldtype: "Date", placeholder: __("From Date") }),
			to_date: make({ fieldname: "to_date", fieldtype: "Date", placeholder: __("To Date") }),
			village: make({ fieldname: "village", fieldtype: "Link", options: "Farm Village", placeholder: __("Village") }),
		};
		// search as you type, not only on blur
		const search = this.controls.search;
		search.$input.on("input", frappe.utils.debounce(() => this.set_filter("search", search.get_value()), 350));
	}

	set_filter(key, value) {
		value = value || (key === "search" ? "" : null);
		if (this.filters[key] === value) return;
		this.filters[key] = value;
		this.start = 0;
		this.load_list();
	}

	clear_filters() {
		Object.keys(this.controls).forEach((k) => {
			this.filters[k] = k === "search" ? "" : null;
			this.controls[k].set_value("");
		});
		this.start = 0;
		this.load_list();
	}

	has_filters() {
		return Object.values(this.filters).some((v) => v);
	}

	// ── data ──────────────────────────────────────────────────────────
	show(crop) {
		if (crop) this.crop = crop;
		this.refresh();
	}

	refresh() {
		this.load_templates();
		return frappe.call({ method: BD_METHOD + "get_overview" }).then((r) => {
			this.overview = r.message;
			const tabs = this.overview.tabs;
			if (!tabs.some((t) => t.crop === this.crop)) {
				this.crop = this.saved_tab();
				if (!tabs.some((t) => t.crop === this.crop)) this.crop = tabs[0].crop;
			}
			this.render_kpis();
			this.render_tabs();
			this.render_recent();
			this.render_fertilizers();
			this.load_list();
		});
	}

	select_crop(crop, focus) {
		if (crop !== this.crop) {
			this.crop = crop;
			this.start = 0;
			this.save_tab(crop);
			this.render_tabs();
			this.load_list();
		}
		if (focus) this.$main.find(`.fa-tab[data-crop="${CSS.escape(crop)}"]`).trigger("focus");
	}

	/** Arrow keys, Home and End move between crop tabs (WAI-ARIA tabs pattern). */
	tab_keydown(e) {
		const crops = this.overview.tabs.map((t) => t.crop);
		const i = crops.indexOf(this.crop);
		const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: crops.length - 1 }[e.key];
		if (next === undefined) return;
		e.preventDefault();
		this.select_crop(crops[(next + crops.length) % crops.length], true);
	}

	page_to(start) {
		this.start = Math.max(0, start);
		this.load_list();
	}

	load_list() {
		const tab = this.current_tab();
		this.render_toolbar(tab);
		if (!tab) return;
		const $list = this.$main.find(".fa-list");
		this.$main.find(".fa-pager").empty();
		if (!tab.exists) {
			this.set_result_info("");
			$list.html(this.empty_state(bd_esc(__("Crop {0} is not in the Farm Crop master.", [tab.crop]))));
			return;
		}
		const seq = ++this.list_seq;
		this.set_result_info(__("Loading…"));
		$list.attr("aria-busy", "true");
		frappe.call({
			method: BD_METHOD + "get_crop_recommendations",
			args: { crop: tab.crop, ...this.filters, start: this.start, page_length: BD_PAGE_LENGTH },
		}).then((r) => {
			if (seq !== this.list_seq) return; // a newer tab or filter has asked again
			$list.attr("aria-busy", "false");
			this.render_list(tab, r.message);
		});
	}

	// ── rendering ─────────────────────────────────────────────────────
	render_kpis() {
		const t = this.overview.totals;
		const cards = [
			[__("Total Recommendations"), format_number(t.count, null, 0)],
			[__("This Month"), format_number(t.this_month, null, 0)],
			[__("Total Plants"), t.plants],
			[__("Total Fertilizer (kg)"), t.qty_kg],
			[__("Total Cost"), t.amount],
		];
		this.$main.find(".fa-kpis").html(cards.map(([label, value]) => `
			<div class="fa-kpi">
				<div class="fa-kpi-label" title="${bd_esc(label)}">${bd_esc(label)}</div>
				<div class="fa-kpi-value">${bd_esc(value)}</div>
			</div>`).join(""));
	}

	render_tabs() {
		this.$main.find(".fa-tabs").html(this.overview.tabs.map((t) => {
			const active = t.crop === this.crop;
			return `<button type="button" role="tab" class="fa-tab${active ? " active" : ""}"
				data-crop="${bd_esc(t.crop)}" aria-selected="${active}" aria-controls="fa-crop-panel"
				tabindex="${active ? 0 : -1}">
				<span class="fa-tab-label">${bd_crop_label(t)}</span>
				<span class="fa-count" aria-label="${bd_esc(__("{0} recommendations", [cint(t.count)]))}">${cint(t.count)}</span>
			</button>`;
		}).join(""));
		// on a narrow screen the tab strip scrolls; keep the selected crop in view
		const active = this.$main.find(".fa-tab.active").get(0);
		if (active) active.scrollIntoView({ block: "nearest", inline: "nearest" });
	}

	render_toolbar(tab) {
		const label = tab ? bd_crop_label(tab) : "";
		this.$main.find(".fa-new")
			.html(`${frappe.utils.icon("add", "xs")}<span>${__("New {0} Recommendation", [label])}</span>`)
			.prop("disabled", !(tab && tab.exists));
		this.$main.find(".fa-list").attr("aria-label", label);
	}

	set_result_info(html) {
		this.$main.find(".fa-result-info").html(html);
	}

	render_list(tab, data) {
		const $list = this.$main.find(".fa-list");
		const crop = bd_crop_label(tab);
		const clear = this.has_filters()
			? `<button type="button" class="btn btn-link btn-xs fa-clear">${__("Clear Filters")}</button>` : "";
		const count = data.total === 1 ? __("1 recommendation") : __("{0} recommendations", [data.total]);
		this.set_result_info(`<span class="fa-result-count">${count}</span>${clear}`);

		if (!data.rows.length) {
			if (this.has_filters()) {
				$list.html(this.empty_state(__("No {0} recommendations match these filters.", [crop]),
					__("Try a different search or date range."),
					`<button type="button" class="btn btn-default btn-sm fa-clear">${__("Clear Filters")}</button>`));
				return;
			}
			const hint = tab.has_template
				? __("Recommendations that include {0} will appear here.", [crop])
				: __("{0} has no default fertilizer template yet. Add fertilizer rows on the recommendation.", [crop]);
			$list.html(this.empty_state(__("No {0} recommendations yet.", [crop]), hint,
				`<button type="button" class="btn btn-primary btn-sm fa-empty-new">
					${frappe.utils.icon("add", "xs")}<span>${__("New Recommendation")}</span></button>`));
			return;
		}

		const cols = [
			["id", __("Recommendation ID")], ["farmer", __("Farmer")], ["village", __("Village")],
			["variety", __("Variety")], ["area", __("Area")], ["plants", __("Plant Count"), "r"],
			["date", __("Date")], ["crop_cost", __("Crop Cost"), "r"], ["total", __("Total Cost"), "r"],
		];
		const label = Object.fromEntries(cols.map(([k, l]) => [k, bd_esc(l)]));
		const body = data.rows.map((d) => {
			// the customer is shown only when it differs from the farmer's name
			const sub = [d.customer !== d.farmer_name ? d.customer : "", d.mobile_no].filter(Boolean);
			return `<tr>
				<td class="fa-c-id" data-label="${label.id}">
					<a href="${frappe.utils.get_form_link(BD_DOCTYPE, d.name)}">${bd_esc(d.name)}</a></td>
				<td class="fa-c-farmer" data-label="${label.farmer}"><div>
					<div class="fa-strong">${bd_esc(d.farmer_name) || "—"}</div>
					${sub.length ? `<div class="fa-muted">${sub.map(bd_esc).join(" · ")}</div>` : ""}</div></td>
				<td data-label="${label.village}">${bd_esc(d.village) || "—"}</td>
				<td data-label="${label.variety}">${bd_esc(d.variety) || "—"}</td>
				<td class="nowrap" data-label="${label.area}">${bd_esc(d.area) || "—"}</td>
				<td class="r num" data-label="${label.plants}">${bd_esc(d.plants)}</td>
				<td class="nowrap" data-label="${label.date}">${bd_esc(d.date)}</td>
				<td class="r num nowrap" data-label="${label.crop_cost}">${bd_esc(d.crop_cost)}</td>
				<td class="r num nowrap fa-strong" data-label="${label.total}">${bd_esc(d.grand_total)}</td>
			</tr>`;
		}).join("");
		$list.html(`<div class="fa-table-wrap"><table class="fa-table fa-table-stack">
			<thead><tr>${cols.map(([, h, cls]) => `<th scope="col" class="${cls || ""}">${bd_esc(h)}</th>`).join("")}</tr></thead>
			<tbody>${body}</tbody></table></div>`);

		if (data.total <= data.page_length) return;
		const from = data.start + 1;
		const to = data.start + data.rows.length;
		this.$main.find(".fa-pager").html(`
			<span class="fa-muted">${__("Showing {0}–{1} of {2}", [from, to, data.total])}</span>
			<span class="fa-pager-buttons">
				<button type="button" class="btn btn-default btn-xs fa-prev" ${data.start ? "" : "disabled"}>
					${__("Previous")}</button>
				<button type="button" class="btn btn-default btn-xs fa-next" ${to < data.total ? "" : "disabled"}>
					${__("Next")}</button>
			</span>`);
	}

	render_recent() {
		const rows = this.overview.recent;
		const $el = this.$main.find(".fa-recent");
		if (!rows.length) {
			$el.html(this.empty_state(__("No recommendations yet."), null, null, true));
			return;
		}
		$el.html(`<div class="fa-table-wrap"><table class="fa-table">
			<thead><tr><th scope="col">${__("Farmer")}</th><th scope="col">${__("Crops")}</th>
				<th scope="col">${__("Date")}</th><th scope="col" class="r">${__("Total Cost")}</th></tr></thead>
			<tbody>${rows.map((d) => `<tr>
				<td><a class="fa-strong" href="${frappe.utils.get_form_link(BD_DOCTYPE, d.name)}">
					${bd_esc(d.farmer_name || d.name)}</a><div class="fa-muted">${bd_esc(d.name)}</div></td>
				<td>${bd_esc(d.crops) || "—"}</td>
				<td class="nowrap">${bd_esc(d.date)}</td>
				<td class="r num nowrap fa-strong">${bd_esc(d.amount)}</td>
			</tr>`).join("")}</tbody></table></div>`);
	}

	render_fertilizers() {
		const rows = this.overview.fertilizers;
		const $el = this.$main.find(".fa-fert");
		if (!rows.length) {
			$el.html(this.empty_state(__("No fertilizer rows yet."), null, null, true));
			return;
		}
		$el.html(`<div class="fa-table-wrap"><table class="fa-table">
			<thead><tr><th scope="col">${__("Fertilizer")}</th><th scope="col" class="r">${__("Pack (kg)")}</th>
				<th scope="col" class="r">${__("Quantity (kg)")}</th><th scope="col" class="r">${__("Amount")}</th></tr></thead>
			<tbody>${rows.map((f) => `<tr><td>${bd_esc(f.fertilizer_name)}</td>
				<td class="r num">${bd_esc(f.pack_kg)}</td><td class="r num">${bd_esc(f.qty_kg)}</td>
				<td class="r num nowrap">${bd_esc(f.amount)}</td></tr>`).join("")}</tbody>
			</table></div>`);
	}

	/** title, hint and action are HTML: escape record data before passing it in. */
	empty_state(title, hint, action, compact) {
		return `<div class="fa-empty${compact ? " fa-empty-compact" : ""}">
			<div class="fa-empty-icon" aria-hidden="true">${frappe.utils.icon("sprout", "md")}</div>
			<div class="fa-empty-title">${title}</div>
			${hint ? `<div class="fa-empty-hint">${hint}</div>` : ""}
			${action ? `<div class="fa-empty-action">${action}</div>` : ""}
		</div>`;
	}

	// ── fertilizer templates ──────────────────────────────────────────
	load_templates() {
		return frappe.call({ method: BD_TEMPLATES }).then((r) => {
			this.templates = r.message;
			this.$main.find(".fa-tpl-add").toggleClass("hidden", !this.templates.can_write);
			if (this.templates.can_write && !this.template_menu) {
				this.template_menu = this.page.add_menu_item(__("Add Template"), () => this.edit_template(null));
			}
			this.render_templates();
		});
	}

	render_templates() {
		if (!this.templates) return;
		const q = (this.$main.find(".fa-tpl-search").val() || "").trim().toLowerCase();
		const status = this.$main.find(".fa-tpl-filter").val();
		const write = this.templates.can_write;
		const rows = this.templates.crops.filter((c) => {
			const has = c.fertilizers.length > 0;
			if (status === "with" && !has) return false;
			if (status === "without" && has) return false;
			return !q || [c.crop, ...c.fertilizers].some((s) => s.toLowerCase().includes(q));
		});
		const $list = this.$main.find(".fa-tpl-list");
		if (!rows.length) {
			$list.html(this.empty_state(__("No crops match."), __("Try another search or status."), null, true));
			return;
		}
		const shown = 4;
		const btn = (cls, label, crop) =>
			`<button type="button" class="btn btn-default btn-xs ${cls}" data-crop="${bd_esc(crop)}">${label}</button>`;
		$list.html(`<div class="fa-table-wrap"><table class="fa-table fa-table-stack">
			<thead><tr><th scope="col">${__("Crop")}</th><th scope="col">${__("Fertilizers")}</th>
				<th scope="col">${__("Status")}</th><th scope="col">${__("Last Updated")}</th>
				<th scope="col" class="r">${__("Actions")}</th></tr></thead>
			<tbody>${rows.map((c) => {
				const has = c.fertilizers.length > 0;
				const names = c.fertilizers.slice(0, shown).map(bd_esc).join(", ")
					+ (c.fertilizers.length > shown ? ` ${__("and {0} more", [c.fertilizers.length - shown])}` : "");
				const actions = !write ? btn("fa-tpl-edit", __("View"), c.crop)
					: has ? btn("fa-tpl-edit", __("Edit"), c.crop) + btn("fa-tpl-delete", __("Delete"), c.crop)
					: btn("fa-tpl-edit", __("Create Template"), c.crop);
				return `<tr>
					<td class="fa-strong" data-label="${bd_esc(__("Crop"))}">${bd_esc(__(c.crop))}</td>
					<td data-label="${bd_esc(__("Fertilizers"))}">${has
						? `<span class="fa-strong">${c.fertilizers.length}</span> <span class="fa-muted">${names}</span>`
						: "—"}</td>
					<td data-label="${bd_esc(__("Status"))}"><span class="fa-pill ${has ? "fa-pill-ok" : "fa-pill-missing"}">
						${has ? __("Template ready") : __("No template")}</span></td>
					<td class="nowrap" data-label="${bd_esc(__("Last Updated"))}"><div>${bd_esc(c.modified)}</div>
						<div class="fa-muted">${bd_esc(c.modified_by)}</div></td>
					<td class="r" data-label="${bd_esc(__("Actions"))}"><div class="fa-tpl-actions">${actions}</div></td>
				</tr>`;
			}).join("")}</tbody></table></div>`);
	}

	edit_template(crop) {
		// a save or delete changes which crops have a template: reload the list and the tab hints
		const done = () => this.refresh();
		farm_advisory.template_editor(crop, { on_save: done, on_delete: done });
	}

	// ── actions ───────────────────────────────────────────────────────
	current_tab() {
		return this.overview && this.overview.tabs.find((t) => t.crop === this.crop);
	}

	new_recommendation() {
		const tab = this.current_tab();
		// read by the form's onload: start with this crop instead of the prototype's Mango
		farm_advisory.basal_start_crop = tab && tab.exists ? tab.crop : null;
		frappe.new_doc(BD_DOCTYPE);
	}

	open_report(report, options) {
		frappe.route_options = options || null;
		frappe.set_route("query-report", report);
	}

	saved_tab() {
		try {
			return localStorage.getItem(BD_TAB_KEY);
		} catch (e) {
			return null;
		}
	}

	save_tab(crop) {
		try {
			localStorage.setItem(BD_TAB_KEY, crop);
		} catch (e) {
			// private window or blocked storage: the tab is simply not remembered
		}
	}
}

function bd_esc(value) {
	return frappe.utils.escape_html(value == null ? "" : String(value));
}

/** The tab label is the stored Farm Crop name. */
function bd_crop_label(tab) {
	return bd_esc(__(tab.crop));
}
