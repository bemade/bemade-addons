# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""Post-migration: refill PO numbers left empty by the shared compute.

Before 19.0.1.5.0, po_numbers, carrier_id and ship_date shared one compute
method. Saving the form wrote carrier_id / ship_date, which protected
po_numbers from recomputation, so commercial invoices built from deliveries
could be stored with no PO numbers. Recompute them where they are empty.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    invoices = env["commercial.invoice"].search(
        [("po_numbers", "in", [False, ""]), ("picking_ids", "!=", False)]
    )
    invoices._compute_po_numbers()
    invoices.flush_recordset(["po_numbers"])
