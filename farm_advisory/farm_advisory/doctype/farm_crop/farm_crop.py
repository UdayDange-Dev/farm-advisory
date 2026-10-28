# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr, flt

from farm_advisory.utils.basal_calc import RATE_UNITS
from farm_advisory.utils.masters import clean_name

# The editable columns of a template row; anything else sent by a client is refused.
TEMPLATE_FIELDS = ("fertilizer", "rate", "rate_unit", "pack_kg", "cost_per_bag", "contains")


class FarmCrop(Document):
	def validate(self):
		clean_name(self, "crop_name")
		self.validate_fertilizer_template()

	def validate_fertilizer_template(self):
		"""Every template row must give Load Template a usable, priced row.

		A pack size or bag price of 0 means "use the fertilizer master", as in the
		prototype, so the check is on the value that will actually be used.
		"""
		before = self.get_doc_before_save()
		old = {r.name: r.fertilizer for r in (before.get("fertilizer_template") or [])} if before else {}
		rows = self.get("fertilizer_template") or []
		masters = _masters([r.fertilizer for r in rows])
		seen = set()
		for row in rows:
			label = _("Template row {0} ({1})").format(row.idx, row.fertilizer or _("no fertilizer"))
			if row.fertilizer in seen:
				frappe.throw(_("Template row {0}: {1} is listed twice.").format(row.idx, row.fertilizer))
			seen.add(row.fertilizer)
			if flt(row.rate) <= 0:
				frappe.throw(_("{0}: enter a rate greater than 0.").format(label))
			if row.rate_unit not in RATE_UNITS:
				frappe.throw(_("{0}: the unit must be one of {1}.").format(label, ", ".join(RATE_UNITS)))
			if flt(row.pack_kg) < 0 or flt(row.cost_per_bag) < 0:
				frappe.throw(_("{0}: pack size and bag price cannot be negative.").format(label))
			m = masters.get(row.fertilizer)
			if not m:
				continue  # Frappe's link check reports a fertilizer that does not exist
			if old.get(row.name) != row.fertilizer and not m.is_active:
				frappe.throw(
					_("{0}: {1} is inactive in the fertilizer master.").format(label, row.fertilizer)
				)
			if flt(row.pack_kg) <= 0 and flt(m.pack_kg) <= 0:
				frappe.throw(
					_("{0}: enter a pack size. The fertilizer master has none to use.").format(label)
				)
			if flt(row.cost_per_bag) <= 0 and flt(m.cost_per_bag) <= 0:
				frappe.throw(
					_("{0}: enter a bag price. The fertilizer master has none to use.").format(label)
				)


# ── template management (Basal Dose page and recommendation form) ─────
# Reading needs read on Farm Crop. Changing a template saves the Farm Crop, so
# the standard write permission and the validation above always apply.


@frappe.whitelist()
def get_template_overview():
	"""Every Basal Dose crop with its template's fertilizers, for the template list."""
	frappe.has_permission("Farm Crop", "read", throw=True)
	crops = frappe.get_list(
		"Farm Crop",
		filters={"used_in_basal": 1},
		fields=["name", "modified", "modified_by"],
		order_by="name asc",
	)
	rows = {}
	if crops:
		for r in frappe.get_all(
			"Farm Crop Fertilizer Template",
			filters={"parenttype": "Farm Crop", "parent": ["in", [c.name for c in crops]]},
			fields=["parent", "fertilizer"],
			order_by="idx asc",
		):
			rows.setdefault(r.parent, []).append(r.fertilizer)
	return {
		"can_write": bool(frappe.has_permission("Farm Crop", "write")),
		"crops": [
			{
				"crop": c.name,
				"fertilizers": rows.get(c.name, []),
				"modified": frappe.format(c.modified, {"fieldtype": "Datetime"}),
				"modified_by": frappe.utils.get_fullname(c.modified_by),
			}
			for c in crops
		],
	}


@frappe.whitelist()
def get_template(crop):
	"""A crop's template rows as saved, with the master values a 0 falls back to."""
	doc = _crop(crop, "read")
	masters = _masters([r.fertilizer for r in doc.fertilizer_template])
	return {
		"crop": doc.name,
		"can_write": bool(doc.has_permission("write")),
		"rows": [
			{
				**{f: r.get(f) for f in TEMPLATE_FIELDS},
				"master_pack_kg": flt((masters.get(r.fertilizer) or {}).get("pack_kg")),
				"master_cost_per_bag": flt((masters.get(r.fertilizer) or {}).get("cost_per_bag")),
			}
			for r in doc.fertilizer_template
		],
	}


@frappe.whitelist(methods=["POST"])
def save_template(crop, rows):
	"""Replace a crop's template with ``rows`` (at least one row)."""
	doc = _crop(crop, "write")
	if isinstance(rows, str):
		try:
			rows = frappe.parse_json(rows)
		except ValueError:
			rows = None
	if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
		frappe.throw(_("Template rows must be a list."))
	if not rows:
		frappe.throw(_("Add at least one fertilizer row, or use Delete Template."))
	clean = []
	for i, r in enumerate(rows, start=1):
		# grid bookkeeping keys are dropped; any other unknown key is refused
		unknown = set(r) - set(TEMPLATE_FIELDS) - {"idx", "name", "doctype", "__islocal", "__unsaved"}
		if unknown:
			frappe.throw(_("Template row {0}: unknown field {1}.").format(i, ", ".join(sorted(unknown))))
		if not r.get("fertilizer"):
			frappe.throw(_("Template row {0}: choose a fertilizer.").format(i))
		clean.append(
			{
				"fertilizer": cstr(r["fertilizer"]),
				"rate": flt(r.get("rate")),
				# a missing unit is left for validation to report, never guessed
				"rate_unit": cstr(r.get("rate_unit")),
				"pack_kg": flt(r.get("pack_kg")),
				"cost_per_bag": flt(r.get("cost_per_bag")),
				"contains": cstr(r.get("contains")).strip() or None,
			}
		)
	doc.set("fertilizer_template", clean)
	doc.save()
	return get_template(doc.name)


@frappe.whitelist(methods=["POST"])
def delete_template(crop):
	"""Remove a crop's template rows. The crop itself is kept."""
	doc = _crop(crop, "write")
	doc.set("fertilizer_template", [])
	doc.save()
	return {"crop": doc.name, "rows": []}


def _crop(crop, ptype):
	crop = cstr(crop)
	if not crop or not frappe.db.exists("Farm Crop", crop):
		frappe.throw(_("Unknown crop: {0}").format(crop), frappe.DoesNotExistError)
	doc = frappe.get_doc("Farm Crop", crop)
	doc.check_permission(ptype)
	return doc


def _masters(names):
	names = list({n for n in names if n})
	if not names:
		return {}
	return {
		m.name: m
		for m in frappe.get_all(
			"Farm Fertilizer",
			filters={"name": ["in", names]},
			fields=["name", "pack_kg", "cost_per_bag", "is_active"],
		)
	}
