"""Re-run the idempotent setup: grants the Farm Advisory roles read access to
ERPNext Address, used by the Customer address fetch on every calculator."""

from farm_advisory.setup.install import setup


def execute():
	setup()
