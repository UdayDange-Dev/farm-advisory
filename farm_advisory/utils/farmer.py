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
		self.validate_customer_address()

	def validate_customer_address(self):
		"""The chosen Address must belong to the chosen Customer."""
		address = self.get("customer_address")
		if not address:
			return
		if not self.customer or address not in linked_addresses(self.customer):
			frappe.throw(
				_("Address {0} is not linked to Customer {1}.").format(address, self.customer or "-"),
				title=_("Invalid Address"),
			)
		if not (self.get("address_display") or "").strip():
			self.address_display = address_text(address)

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
		local = any(self.get(f) for f in ("village", "taluka", "district"))
		if not local and (self.get("address_display") or "").strip():
			# no Farm Village / Taluka / District picked (State alone, which defaults
			# to Maharashtra, is not an address): print the fetched ERPNext Address
			return ", ".join(x.strip() for x in self.address_display.splitlines() if x.strip())
		return line


# --------------------------------------------------------------------------- #
# ERPNext Address
# --------------------------------------------------------------------------- #
ADDRESS_FIELDS = ("address_line1", "address_line2", "city", "county", "state", "pincode", "country")


def linked_addresses(customer):
	"""Enabled Address records linked to a Customer, best candidate first.

	Order: the Customer's ``customer_primary_address``, then addresses marked
	primary, then shipping, then the most recently modified.
	"""
	if not customer:
		return []
	names = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Address", "link_doctype": "Customer", "link_name": customer},
		pluck="parent",
	)
	if not names:
		return []
	rows = frappe.get_all(
		"Address",
		filters={"name": ["in", names], "disabled": 0},
		fields=["name", "is_primary_address", "is_shipping_address", "modified"],
		order_by="is_primary_address desc, is_shipping_address desc, modified desc",
	)
	primary = frappe.db.get_value("Customer", customer, "customer_primary_address")
	ordered = [r.name for r in rows]
	if primary in ordered:
		ordered.remove(primary)
		ordered.insert(0, primary)
	return ordered


def address_text(address):
	"""An Address as plain multi-line text (no HTML), for a Small Text field."""
	a = frappe.db.get_value("Address", address, ADDRESS_FIELDS, as_dict=True) if address else None
	if not a:
		return ""
	city_line = ", ".join(p for p in (a.city, a.county) if p)
	state_line = " – ".join(p for p in (a.state, a.pincode) if p)
	lines = [a.address_line1, a.address_line2, city_line, state_line]
	if a.country and a.country != "India":
		lines.append(a.country)
	return "\n".join(x.strip() for x in lines if x and x.strip())


def _masters_text(values):
	"""Fallback address from the Farm Village / Taluka / District / State fields."""
	parts = [values.get(f) for f in ("village", "taluka", "district", "state") if values.get(f)]
	line = ", ".join(parts)
	if values.get("pin_code"):
		line = f"{line} – {values['pin_code']}" if line else values["pin_code"]
	return line


def _address_values(customer, current):
	"""``customer_address`` / ``address_display`` for ``customer``, plus any
	PIN / State the Address can supply that the Customer's own fields lack."""
	addresses = linked_addresses(customer)
	address = addresses[0] if addresses else None
	out = {"customer_address": address or "", "address_count": len(addresses)}
	if address:
		a = frappe.db.get_value("Address", address, ["pincode", "state"], as_dict=True) or {}
		pin = "".join(ch for ch in (a.get("pincode") or "") if ch.isdigit())
		if not current.get("pin_code") and len(pin) == 6:
			out["pin_code"] = pin
		if not current.get("state") and a.get("state") and frappe.db.exists("Farm State", a["state"]):
			out["state"] = a["state"]
		out["address_display"] = address_text(address)
	else:
		out["address_display"] = _masters_text({**current, **out})
	return out


@frappe.whitelist()
def get_address_display(customer, address):
	"""Text of one of a Customer's addresses (the form's Address picker)."""
	frappe.has_permission("Customer", "read", customer, throw=True)
	if address not in linked_addresses(customer):
		frappe.throw(_("Address {0} is not linked to Customer {1}.").format(address, customer))
	return address_text(address)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def customer_address_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link query for ``customer_address``: only the chosen Customer's addresses.

	Checked against Customer read permission, so an advisor who may open the
	farmer can pick the farmer's address without wider Address access.
	"""
	customer = (filters or {}).get("customer")
	if not customer:
		return []
	frappe.has_permission("Customer", "read", customer, throw=True)
	names = linked_addresses(customer)
	if txt:
		t = txt.lower()
		names = [
			n for n in names if t in n.lower() or t in (address_text(n) or "").lower().replace("\n", " ")
		]
	names = names[int(start) : int(start) + int(page_len)]
	return [(n, (address_text(n) or "").replace("\n", ", ")) for n in names]


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
	# The address always comes back (possibly empty), so switching to another
	# farmer never leaves the previous farmer's address on the form.
	out.update(_address_values(customer, out))
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
