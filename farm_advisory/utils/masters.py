import re


def clean_name(doc, fieldname, upper=False):
	"""Trim and collapse spaces so "Loni " and "Loni" cannot both exist.

	The database key is already case-insensitive, which blocks "loni" vs "Loni".
	"""
	value = re.sub(r"\s+", " ", (doc.get(fieldname) or "")).strip()
	doc.set(fieldname, value.upper() if upper else value)
