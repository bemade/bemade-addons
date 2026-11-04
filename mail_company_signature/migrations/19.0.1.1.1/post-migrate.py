from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Re-render generated signatures single-spaced."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["res.users"].with_context(active_test=False).search([])
    users._company_signature_enforced_users()._compute_signature()
