"""Number helpers that reproduce the browser prototypes exactly.

The reference calculators were written in JavaScript, so two behaviours matter:

* ``Math.round`` rounds .5 *up*; Python's ``round`` rounds half to even.
* ``toLocaleString('en-IN', ...)`` groups digits the Indian way (12,34,567)
  and drops trailing zeros unless a minimum is asked for.
"""

import math

from frappe.utils import flt


def js_round(x):
	"""JavaScript ``Math.round``: halves go towards +infinity."""
	return math.floor(flt(x) + 0.5)


def num(v):
	"""``parseFloat`` with a 0 fallback, as the prototypes' ``num()``."""
	try:
		x = float(v)
	except TypeError, ValueError:
		return 0.0
	return x if math.isfinite(x) else 0.0


def _group_indian(int_part):
	s = str(int_part)
	if len(s) <= 3:
		return s
	head, tail = s[:-3], s[-3:]
	groups = []
	while len(head) > 2:
		groups.insert(0, head[-2:])
		head = head[:-2]
	if head:
		groups.insert(0, head)
	return ",".join(groups) + "," + tail


def fmt(v, max_dp=2, min_dp=0):
	"""``Number.toLocaleString('en-IN', {min/maxFractionDigits})``."""
	x = num(v)
	neg = x < 0
	x = abs(x)
	# round half away from zero at the requested precision, like Intl does
	factor = 10**max_dp
	scaled = math.floor(x * factor + 0.5 + 1e-9)
	int_part, frac = divmod(scaled, factor)
	frac_s = str(frac).rjust(max_dp, "0") if max_dp else ""
	frac_s = frac_s.rstrip("0")
	if len(frac_s) < min_dp:
		frac_s = frac_s.ljust(min_dp, "0")
	out = _group_indian(int_part) + ("." + frac_s if frac_s else "")
	return ("-" if neg and (int_part or frac) else "") + out


def inr(v):
	"""``'₹ ' + n.toLocaleString('en-IN', {min:2, max:2})`` (Spray prototype)."""
	return "₹ " + fmt(v, 2, 2)


def inr0(v):
	"""``'₹ ' + n.toLocaleString('en-IN', {max:0})`` (Basal prototype)."""
	return "₹ " + fmt(v, 0)
