from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    so_visibility_draft_state = fields.Boolean(
        string="Hide SO Lines in Draft State",
        default=False,
        help="If enabled, sales order lines will be hidden in the portal when the "
        "sales order is in draft state.",
    )
