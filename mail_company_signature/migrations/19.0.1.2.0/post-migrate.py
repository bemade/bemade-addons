from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Regenerate enforced signatures: the cell line now needs the new
    "Show cell phone in email signature" box (hidden by default).

    Only users under an enforced policy are recomputed, so this is a no-op
    when no company enforces it. Safe to run again.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    users = env["res.users"].with_context(active_test=False).search([])
    users._company_signature_enforced_users()._compute_signature()
