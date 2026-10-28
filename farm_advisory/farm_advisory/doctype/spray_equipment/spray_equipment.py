# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from farm_advisory.utils.masters import clean_name


class SprayEquipment(Document):
	def validate(self):
		clean_name(self, "equipment_name")
		if flt(self.tank_capacity) <= 0:
			frappe.throw(_("Tank Capacity must be greater than zero."))
