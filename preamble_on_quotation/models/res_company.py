from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    default_quotation_preamble = fields.Html(
        string="Default Quotation Preamble",
        help="Default HTML content to display at the beginning of quotation PDFs",
        sanitize=True,
        sanitize_tags=True,
    )
