# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from farm_advisory.utils.consultation_calc import apply_consultation_calculation
from farm_advisory.utils.farmer import FarmerMixin
from farm_advisory.utils.i18n import lang_key


class CropConsultation(FarmerMixin, Document):
	def get_lang(self):
		return lang_key(self.report_language)

	def validate(self):
		self.set_farmer_fields()
		self.validate_blocks()
		self.validate_coordinates()
		self.validate_ranges()
		apply_consultation_calculation(self)
		self.validate_status()

	def validate_blocks(self):
		for b in self.get("crop_blocks") or []:
			if b.variety:
				crop = frappe.db.get_value("Farm Crop Variety", b.variety, "crop")
				if crop and crop != b.crop:
					frappe.throw(
						_("Crop block {0}: variety {1} belongs to {2}, not {3}.").format(
							b.idx, b.variety, crop, b.crop
						)
					)
		n = len(self.get("crop_blocks") or [])
		for p in self.get("problems") or []:
			if cint(p.block_no) > n:
				frappe.throw(
					_("Diagnosis case {0}: crop block {1} does not exist.").format(p.idx, p.block_no),
					title=_("Unknown Crop Block"),
				)

	def validate_coordinates(self):
		if not (-90 <= flt(self.latitude) <= 90 and -180 <= flt(self.longitude) <= 180):
			frappe.throw(_("Latitude must be between -90 and 90 and longitude between -180 and 180."))

	def validate_ranges(self):
		for r in self.get("ndvi_readings") or []:
			if not -1 <= flt(r.ndvi) <= 1:
				frappe.throw(_("NDVI row {0}: NDVI must be between -1 and 1.").format(r.idx))
		for field, label in (("soil_ph", "Soil pH"), ("water_ph", "Water pH")):
			if flt(self.get(field)) > 14:
				frappe.throw(_("{0} must be between 0 and 14.").format(_(label)))
		for p in self.get("problems") or []:
			if flt(p.affected_pct) > 100:
				frappe.throw(_("Diagnosis case {0}: affected area cannot exceed 100%.").format(p.idx))

	def validate_status(self):
		if self.status in ("Agronomist Approved", "Issued to Farmer") and not (self.agronomist or "").strip():
			frappe.throw(
				_("Enter the approving agronomist before setting the status to {0}.").format(_(self.status)),
				title=_("Agronomist Required"),
			)
