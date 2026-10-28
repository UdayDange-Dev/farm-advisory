# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from farm_advisory.utils.masters import clean_name


class FarmDistrict(Document):
	def validate(self):
		clean_name(self, "district_name")
