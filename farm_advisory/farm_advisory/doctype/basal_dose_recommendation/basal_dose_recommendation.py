# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from farm_advisory.utils.basal_calc import apply_basal_calculation
from farm_advisory.utils.farmer import FarmerMixin


class BasalDoseRecommendation(FarmerMixin, Document):
	def validate(self):
		self.set_farmer_fields()
		self.normalise_crops(strict=True)
		self.drop_blank_rows()
		self.validate_fertilizers()
		self.validate_crops()
		apply_basal_calculation(self)

	def normalise_crops(self, strict=False):
		"""Number crops 1..n in row order and keep each fertilizer with its crop.

		A fertilizer row is matched to its crop by the crop's number *before*
		renumbering, so the rows of a removed crop are never handed to the crop
		that takes its number. A crop that arrived without a number keeps its
		position as its number.
		"""
		remap, unnumbered = {}, set()
		for i, c in enumerate(self.get("crops") or [], start=1):
			if c.crop_no:
				if strict and c.crop_no in remap:
					frappe.throw(
						_("Crop No. {0} is used by more than one crop.").format(c.crop_no),
						title=_("Duplicate Crop"),
					)
				remap.setdefault(c.crop_no, i)
			else:
				unnumbered.add(i)
			c.crop_no = i
		for r in self.get("fertilizers") or []:
			if r.crop_no in remap:
				r.crop_no = remap[r.crop_no]
			elif strict and r.crop_no not in unnumbered:
				frappe.throw(
					_("Fertilizer row {0}: Crop No. {1} does not exist.").format(r.idx, r.crop_no),
					title=_("Unknown Crop"),
				)

	def drop_blank_rows(self):
		"""The prototype starts a crop with an empty row; do not store those."""
		rows = [
			r for r in (self.get("fertilizers") or []) if r.fertilizer or r.fertilizer_name or flt(r.rate)
		]
		if len(rows) != len(self.get("fertilizers") or []):
			self.set("fertilizers", rows)

	def validate_fertilizers(self):
		before = self.get_doc_before_save()
		old = {r.name: r.fertilizer for r in (before.get("fertilizers") or [])} if before else {}
		crops = {c.crop_no: c.crop for c in self.get("crops") or []}
		for r in self.get("fertilizers") or []:
			if not r.fertilizer and not r.fertilizer_name:
				frappe.throw(
					_(
						"{0} (crop {1}): a fertilizer row has no fertilizer. Choose one or delete the row."
					).format(crops.get(r.crop_no) or _("Crop"), r.crop_no)
				)
			if r.fertilizer and (not r.fertilizer_name or old.get(r.name) != r.fertilizer):
				# snapshot: later price or name edits in the master leave this record alone
				r.fertilizer_name = frappe.db.get_value("Farm Fertilizer", r.fertilizer, "fertilizer_name")

	def validate_crops(self):
		for c in self.get("crops") or []:
			if c.variety:
				crop = frappe.db.get_value("Farm Crop Variety", c.variety, "crop")
				if crop and crop != c.crop:
					frappe.throw(
						_("Crop row {0}: variety {1} belongs to {2}, not {3}.").format(
							c.idx, c.variety, crop, c.crop
						)
					)
