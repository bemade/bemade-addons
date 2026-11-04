from odoo import api, fields, models


class BemadeDedupGroupRecord(models.Model):
    """Contact-specific columns for the deduplication review screen.

    The engine deliberately knows nothing about res.partner, so the fields a
    reviewer needs to tell two contacts apart are added here. They resolve
    only for partner rows and stay empty for any other model, which is why
    they are computed rather than related.
    """

    _inherit = "bemade.dedup.group.record"

    partner_parent_id = fields.Many2one(
        "res.partner", string="Company", compute="_compute_partner_fields"
    )
    partner_email = fields.Char(string="Email", compute="_compute_partner_fields")
    partner_phone = fields.Char(string="Phone", compute="_compute_partner_fields")
    partner_city = fields.Char(string="City", compute="_compute_partner_fields")

    @api.depends("res_id", "model_name")
    def _compute_partner_fields(self):
        for line in self:
            partner = line._record() if line.model_name == "res.partner" else None
            line.partner_parent_id = partner.parent_id if partner else False
            line.partner_email = partner.email if partner else False
            line.partner_phone = partner.phone if partner else False
            line.partner_city = partner.city if partner else False
