"""Farmer details on calculator documents, backed by ERPNext Customer.

There is no separate Farmer master: every Spray Schedule / Basal Dose
Recommendation links to a Customer. The farmer fields on the document are a
snapshot (what was printed), pre-filled from the Customer.
"""

import re

import frappe
from frappe import _

# Customer custom field -> document field
CUSTOMER_FIELD_MAP = {
	"fa_first_name": "first_name",
	"fa_middle_name": "middle_name",
	"fa_last_name": "last_name",
	"fa_village": "village",
	"fa_taluka": "taluka",
	"fa_district": "district",
	"fa_state": "state",
	"fa_pin_code": "pin_code",
	"fa_whatsapp_no": "whatsapp_no",
}


def clean_mobile(value, label):
	"""Digits only, 10 digits (a leading 91 / 0 country or trunk prefix is dropped)."""
	if not value:
		return value
	digits = re.sub(r"\D", "", str(value))
	if len(digits) == 12 and digits.startswith("91"):
		digits = digits[2:]
	elif len(digits) == 11 and digits.startswith("0"):
		digits = digits[1:]
	if len(digits) != 10:
		frappe.throw(_("{0} must be a 10 digit number.").format(_(label)), title=_("Invalid Number"))
	return digits


class FarmerMixin:
	"""Validation shared by both calculator documents."""

	def set_farmer_fields(self):
		for f in ("first_name", "middle_name", "last_name"):
			self.set(f, (self.get(f) or "").strip())
		self.farmer_name = " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)
		self.mobile_no = clean_mobile(self.mobile_no, "Mobile Number")
		if self.whatsapp_same_as_mobile:
			self.whatsapp_no = self.mobile_no
		self.whatsapp_no = clean_mobile(self.whatsapp_no, "WhatsApp Number")
		if self.pin_code:
			self.pin_code = re.sub(r"\D", "", str(self.pin_code))
			if len(self.pin_code) != 6:
				frappe.throw(_("PIN Code must be 6 digits."), title=_("Invalid PIN Code"))

	def whatsapp_target(self):
		"""``wa.me`` number: 91 + 10 digits, as in the prototypes."""
		n = re.sub(r"\D", "", self.whatsapp_no or self.mobile_no or "")
		return "91" + n if len(n) == 10 else n

	def address_line(self, lang="en"):
		from farm_advisory.utils.i18n import master

		parts = []
		for field, dt, key in (
			("village", "Farm Village", "village"),
			("taluka", "Farm Taluka", "taluka"),
			("district", "Farm District", "district"),
			("state", "Farm State", "state"),
		):
			value = self.get(field)
			if not value:
				continue
			mr = frappe.db.get_value(dt, value, f"{key}_name_mr") if lang != "en" else None
			parts.append(master(value, mr, lang))
		line = ", ".join(parts)
		if self.pin_code:
			line += " – " + self.pin_code
		return line


def _split_name(full):
	parts = (full or "").split()
	if not parts:
		return "", "", ""
	if len(parts) == 1:
		return parts[0], "", ""
	if len(parts) == 2:
		return parts[0], "", parts[1]
	return parts[0], " ".join(parts[1:-1]), parts[-1]


@frappe.whitelist()
def get_farmer_details(customer):
	"""Values to pre-fill on a calculator when a Customer is chosen."""
	frappe.has_permission("Customer", "read", customer, throw=True)
	c = frappe.get_doc("Customer", customer)
	out = {doc_f: c.get(cust_f) for cust_f, doc_f in CUSTOMER_FIELD_MAP.items() if c.get(cust_f)}
	if not out.get("first_name"):
		first, middle, last = _split_name(c.customer_name)
		out.update(first_name=first, middle_name=middle, last_name=last)
	out["mobile_no"] = c.mobile_no
	out["email_id"] = c.email_id
	if out.get("whatsapp_no") and out["whatsapp_no"] != c.mobile_no:
		out["whatsapp_same_as_mobile"] = 0
	return out


def _default_link(doctype, preferred=None):
	if preferred and frappe.db.exists(doctype, preferred):
		return preferred
	return frappe.db.get_value(doctype, {"is_group": 0}, "name", order_by="creation asc")


@frappe.whitelist()
def create_customer(
	first_name,
	middle_name=None,
	last_name=None,
	mobile_no=None,
	email_id=None,
	whatsapp_no=None,
	village=None,
	taluka=None,
	district=None,
	state=None,
	pin_code=None,
):
	"""Create (or find by mobile number) the Customer for a farmer.

	Returns ``{"customer": name, "existing": bool}``. Matching on mobile number
	stops the same farmer being created twice by different advisors.
	"""
	frappe.has_permission("Customer", "create", throw=True)
	if not (first_name or "").strip():
		frappe.throw(_("Enter the farmer's first name first."))
	mobile = clean_mobile(mobile_no, "Mobile Number")
	if mobile:
		existing = frappe.db.get_value("Customer", {"mobile_no": mobile}, "name")
		if existing:
			return {"customer": existing, "existing": True}

	settings = frappe.get_cached_doc("Farm Advisory Settings")
	full = " ".join(p.strip() for p in (first_name, middle_name, last_name) if p and p.strip())
	cust = frappe.new_doc("Customer")
	cust.customer_name = full
	cust.customer_type = "Individual"
	cust.customer_group = _default_link("Customer Group", settings.customer_group or "Individual")
	cust.territory = _default_link("Territory", settings.territory or "India")
	cust.mobile_no = mobile
	cust.email_id = email_id
	values = dict(
		first_name=first_name,
		middle_name=middle_name,
		last_name=last_name,
		village=village,
		taluka=taluka,
		district=district,
		state=state,
		pin_code=pin_code,
		whatsapp_no=clean_mobile(whatsapp_no, "WhatsApp Number"),
	)
	for cust_f, doc_f in CUSTOMER_FIELD_MAP.items():
		if values.get(doc_f):
			cust.set(cust_f, values[doc_f])
	# permission was checked above; the flag lets ERPNext create the primary
	# Contact for an advisor who has no Contact permission of their own
	cust.insert(ignore_permissions=True)
	return {"customer": cust.name, "existing": False}
