from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company or self.env.user.company_id,
    )

    so_visibility_draft_state = fields.Boolean(
        string="Hide SO Lines in Draft State",
        related="company_id.so_visibility_draft_state",
        readonly=False,
        help="If enabled, sales order lines will be hidden in the portal when the sales order is in draft state.",
    )
