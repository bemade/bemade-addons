from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    mail_signature_position = fields.Selection(
        selection=[
            ("below", "Below the quoted message"),
            ("above", "Above the quoted message"),
        ],
        string="Signature Position",
        default="below",
        required=True,
        help="Where the user's signature is placed in the composer opened by "
        "Reply All and Forward: below the quoted message (Odoo's default) or "
        "right under the typing line, above the quoted message.",
    )
