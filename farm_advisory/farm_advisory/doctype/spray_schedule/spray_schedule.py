# Copyright (c) 2026, Uday Dange and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from farm_advisory.utils.farmer import FarmerMixin
from farm_advisory.utils.i18n import lang_key
from farm_advisory.utils.spray_calc import apply_spray_calculation


class SpraySchedule(FarmerMixin, Document):
	def validate(self):
		self.set_farmer_fields()
		self.normalise_sprays(strict=True)
		self.validate_products()
		self.validate_variety()
		apply_spray_calculation(self)

	def get_lang(self):
		return lang_key(self.report_language)

	# ------------------------------------------------------------------ #
	def normalise_sprays(self, strict=False):
		"""Number sprays 1..n in row order and carry each product with its spray.

		A product pointing at a spray number that does not exist is an error on
		save (``strict``); the live preview just leaves it out of the totals.
		"""
		if not self.get("sprays") and self.get("products"):
			self.append("sprays", {})
		remap = {}
		for i, s in enumerate(self.get("sprays") or [], start=1):
			if s.spray_no:
				remap.setdefault(s.spray_no, i)
			s.spray_no = i
		valid = set(range(1, len(self.get("sprays") or []) + 1))
		for p in self.get("products") or []:
			if p.spray_no in remap:
				p.spray_no = remap[p.spray_no]
			elif strict and p.spray_no not in valid:
				frappe.throw(
					_("Product row {0}: Spray No. {1} does not exist.").format(p.idx, p.spray_no),
					title=_("Unknown Spray"),
				)

	def validate_products(self):
		before = self.get_doc_before_save()
		old = {r.name: r.product for r in (before.get("products") or [])} if before else {}
		for p in self.get("products") or []:
			if not p.product:
				continue
			info = frappe.db.get_value(
				"Spray Product", p.product, ["product_name", "product_name_mr", "category"], as_dict=True
			)
			if not info:
				continue
			# Snapshot the names when the row is new or its product changed, so a
			# later edit of the master never rewrites an already-issued schedule.
			if not p.product_name or old.get(p.name) != p.product:
				p.product_name = info.product_name
				p.product_name_mr = info.product_name_mr
			if p.category and info.category and p.category != info.category:
				frappe.throw(
					_("Product row {0}: {1} is a {2} product, not {3}.").format(
						p.idx, p.product, _(info.category), _(p.category)
					)
				)
			p.category = p.category or info.category

	def validate_variety(self):
		if self.variety and self.crop:
			crop = frappe.db.get_value("Farm Crop Variety", self.variety, "crop")
			if crop and crop != self.crop:
				frappe.throw(_("Variety {0} belongs to {1}, not {2}.").format(self.variety, crop, self.crop))
