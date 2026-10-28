# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from farm_advisory.utils.masters import clean_name


class FarmFertilizer(Document):
	def validate(self):
		# the reference calculator upper-cases every new fertilizer name
		clean_name(self, "fertilizer_name", upper=True)
		if flt(self.pack_kg) <= 0:
			frappe.throw(_("Pack Size must be greater than zero."))
