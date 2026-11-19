"""Install / upgrade steps for Farm Advisory.

Everything here is idempotent: it only creates what is missing and never
overwrites values the business has since edited (prices, names, templates).
Runs from ``after_install`` and from the ``setup_farm_advisory`` patch, so an
existing site picks it up on ``bench migrate``.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from farm_advisory.setup import seed_data as S

ROLES = ("Farm Advisory Manager", "Farm Advisor")
# Tables the app's own files are imported into, which only a migrated Frappe v16.50+ site has.
REQUIRED_FRAMEWORK_TABLES = ("Sidebar", "Sidebar Item")


def before_install():
	"""Refuse to install on a site whose Frappe schema is behind its code.

	Runs before Frappe creates the Module Def or imports any file, so a refusal leaves nothing
	behind. Without it, importing ``sidebar/farm_advisory`` fails half-way with MariaDB 1146
	(``tabSidebar`` doesn't exist) after DocTypes and the Module Def are already committed.
	Reads only.
	"""
	missing = [dt for dt in REQUIRED_FRAMEWORK_TABLES if not frappe.db.table_exists(dt, cached=False)]
	if missing:
		frappe.throw(
			f"Farm Advisory needs Frappe v16.50 or later with its schema migrated, but this site has "
			f"no table for: {', '.join(missing)}. Back up the site, run "
			f"`bench --site {frappe.local.site} migrate`, then install again."
		)


def after_install():
	setup()


def setup():
	create_roles()
	make_custom_fields()
	grant_erpnext_permissions()
	seed_masters()
	seed_settings()
	frappe.db.commit()


# --------------------------------------------------------------------------- #
def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def make_custom_fields():
	create_custom_fields(
		{
			"Customer": [
				dict(
					fieldname="fa_farmer_section",
					fieldtype="Section Break",
					label="Farmer Details",
					insert_after="language",
					collapsible=1,
				),
				dict(
					fieldname="fa_first_name",
					fieldtype="Data",
					label="First Name",
					insert_after="fa_farmer_section",
				),
				dict(
					fieldname="fa_middle_name",
					fieldtype="Data",
					label="Middle Name",
					insert_after="fa_first_name",
				),
				dict(
					fieldname="fa_last_name",
					fieldtype="Data",
					label="Last Name",
					insert_after="fa_middle_name",
				),
				dict(
					fieldname="fa_whatsapp_no",
					fieldtype="Data",
					label="WhatsApp Number",
					options="Phone",
					insert_after="fa_last_name",
				),
				dict(fieldname="fa_farmer_cb", fieldtype="Column Break", insert_after="fa_whatsapp_no"),
				dict(
					fieldname="fa_village",
					fieldtype="Link",
					label="Village",
					options="Farm Village",
					insert_after="fa_farmer_cb",
				),
				dict(
					fieldname="fa_taluka",
					fieldtype="Link",
					label="Taluka",
					options="Farm Taluka",
					insert_after="fa_village",
					in_standard_filter=1,
				),
				dict(
					fieldname="fa_district",
					fieldtype="Link",
					label="District",
					options="Farm District",
					insert_after="fa_taluka",
				),
				dict(
					fieldname="fa_state",
					fieldtype="Link",
					label="State",
					options="Farm State",
					insert_after="fa_district",
				),
				dict(fieldname="fa_pin_code", fieldtype="Data", label="PIN Code", insert_after="fa_state"),
			],
			"Branch": [
				dict(
					fieldname="fa_branch_name_mr",
					fieldtype="Data",
					label="Branch Name (Marathi)",
					insert_after="branch",
				),
				dict(
					fieldname="fa_address",
					fieldtype="Small Text",
					label="Address (for reports)",
					insert_after="fa_branch_name_mr",
				),
				dict(
					fieldname="fa_phone",
					fieldtype="Data",
					label="Phone (for reports)",
					insert_after="fa_address",
				),
			],
		},
		update=True,
	)


def grant_erpnext_permissions():
	"""Advisors pick and create farmers (Customer) and read branches and addresses.

	Uses Custom DocPerm, so ERPNext's own permission files are untouched.
	"""
	for role in ROLES:
		for doctype, rights in (
			("Customer", ("read", "write", "create", "report", "print")),
			("Branch", ("read",)),
			# the farmer address shown on every calculator comes from ERPNext Address
			("Address", ("read",)),
		):
			if frappe.db.exists(
				"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0}
			):
				continue
			add_permission(doctype, role, 0)
			for right in rights:
				update_permission_property(doctype, role, 0, right, 1, validate=False)
			# Custom DocPerm defaults export to 1; only grant what is listed above.
			if "export" not in rights:
				update_permission_property(doctype, role, 0, "export", 0, validate=False)


# --------------------------------------------------------------------------- #
def _insert(doctype, values):
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.insert(ignore_permissions=True)
	return doc


def _ensure(doctype, name, values):
	if not frappe.db.exists(doctype, name):
		_insert(doctype, values)


def seed_masters():
	for dt, key, rows in (
		("Farm Village", "village", S.VILLAGES),
		("Farm Taluka", "taluka", S.TALUKAS),
		("Farm District", "district", S.DISTRICTS),
		("Farm State", "state", S.STATES),
	):
		for en, mr in rows:
			_ensure(dt, en, {f"{key}_name": en, f"{key}_name_mr": mr})

	seed_branches()

	for name, mr, cap in S.SPRAY_EQUIPMENT:
		_ensure(
			"Spray Equipment", name, {"equipment_name": name, "equipment_name_mr": mr, "tank_capacity": cap}
		)

	for category, products in S.SPRAY_PRODUCTS.items():
		for name, mr, unit in products:
			_ensure(
				"Spray Product",
				name,
				{
					"product_name": name,
					"product_name_mr": mr,
					"category": category,
					"default_dose_unit": unit,
				},
			)

	for name, pack, contains, cost in S.FERTILIZERS:
		_ensure(
			"Farm Fertilizer",
			name,
			{"fertilizer_name": name, "pack_kg": pack, "contains": contains, "cost_per_bag": cost},
		)

	for crop, (mr, spray, basal, row_sp, plant_sp) in S.CROPS.items():
		if frappe.db.exists("Farm Crop", crop):
			continue
		template = [
			{
				"fertilizer": t[0],
				"rate": t[1],
				"rate_unit": "gm / plant",
				"pack_kg": t[2] if len(t) > 2 and t[2] else 0,
				"contains": t[3] if len(t) > 3 and t[3] else None,
				"cost_per_bag": t[4] if len(t) > 4 and t[4] is not None else 0,
			}
			for t in S.FERTILIZER_TEMPLATES.get(crop, [])
		]
		_insert(
			"Farm Crop",
			{
				"crop_name": crop,
				"crop_name_mr": mr,
				"used_in_spray": spray,
				"used_in_basal": basal,
				"default_row_spacing": row_sp,
				"default_plant_spacing": plant_sp,
				"fertilizer_template": template,
			},
		)

	varieties = {}
	for crop, rows in S.SPRAY_VARIETIES.items():
		for en, mr in rows:
			varieties.setdefault((crop, en), {"mr": mr, "spray": 1, "basal": 0})
	for crop, rows in S.BASAL_VARIETIES.items():
		for en in rows:
			v = varieties.setdefault((crop, en), {"mr": None, "spray": 0, "basal": 0})
			v["basal"] = 1
	for (crop, en), v in varieties.items():
		_ensure(
			"Farm Crop Variety",
			f"{crop} - {en}",
			{
				"crop": crop,
				"variety_name": en,
				"variety_name_mr": v["mr"],
				"used_in_spray": v["spray"],
				"used_in_basal": v["basal"],
			},
		)


def seed_branches():
	"""Add the Agri Smart branches without touching a site's own Branch master.

	Branch is ERPNext's shared master, so a site that already has branches may name them
	differently (naming rule / renamed records), or carry its own mandatory custom fields.
	Matching only on ``name`` then inserts a duplicate ``branch`` value (unique) or fails
	mandatory checks, and the whole install aborts. Here we:
	  * skip entirely when ``farm_advisory_skip_branch_seed`` is set in site_config.json;
	  * match an existing record on the ``branch`` field as well as on ``name``;
	  * only fill the Marathi / address / phone fields where they are blank;
	  * log and skip a branch that cannot be inserted instead of failing the install.
	Branch is optional on every Farm Advisory form, so a skipped branch breaks nothing.
	"""
	if frappe.conf.get("farm_advisory_skip_branch_seed"):
		return

	for branch, mr, address, phone in S.BRANCHES:
		extra = {"fa_branch_name_mr": mr, "fa_address": address, "fa_phone": phone}
		existing = frappe.db.get_value("Branch", {"branch": branch}, "name") or frappe.db.exists(
			"Branch", branch
		)
		if existing:
			current = frappe.db.get_value("Branch", existing, list(extra), as_dict=True) or {}
			blanks = {k: v for k, v in extra.items() if not current.get(k)}
			if blanks:
				frappe.db.set_value("Branch", existing, blanks, update_modified=False)
			continue

		try:
			frappe.db.savepoint("fa_branch_seed")
			_insert("Branch", {"branch": branch, **extra})
		except Exception:
			frappe.db.rollback(save_point="fa_branch_seed")
			frappe.log_error(
				title=f"Farm Advisory: skipped seeding Branch '{branch}'",
				message=frappe.get_traceback(),
			)


def _first_seeded_branch():
	for branch, *_ in S.BRANCHES:
		name = frappe.db.get_value("Branch", {"branch": branch}, "name")
		if name:
			return name
	return None


def seed_settings():
	s = frappe.get_single("Farm Advisory Settings")
	changed = False
	defaults = {
		"company_name": S.COMPANY_NAME,
		"report_email": S.COMPANY_EMAIL,
		"report_tagline": S.REPORT_TAGLINE,
		# Only point at a branch that really exists, or the Link validation fails the save.
		"default_branch": _first_seeded_branch(),
		"default_report_language": "English + Marathi",
		"default_bag_rounding": "Round up (full bags)",
	}
	for field, value in defaults.items():
		if not s.get(field):
			s.set(field, value)
			changed = True
	if changed:
		s.flags.ignore_permissions = True
		s.save()
