import frappe

APP_ROLES = {"Farm Advisory Manager", "Farm Advisor", "System Manager"}


def has_app_permission():
	"""Who sees the Farm Advisory tile on the /apps screen."""
	if frappe.session.user == "Administrator":
		return True
	return bool(APP_ROLES & set(frappe.get_roles()))
