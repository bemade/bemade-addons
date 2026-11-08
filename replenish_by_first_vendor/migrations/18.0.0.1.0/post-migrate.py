from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Fill the manual lines that earlier versions left without a vendor."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["stock.warehouse.orderpoint"]._fill_missing_supplier()
