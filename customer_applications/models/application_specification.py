from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PartnerApplicationSpecification(models.Model):
    _name = "partner.application.specification"
    _description = "Partner Application Specification"
    _inherit = ["mail.thread", "mail.activity.mixin", "incrementing.sequence.mixin"]
    _sequence_group = "application_id"

    key_id = fields.Many2one(
        comodel_name="partner.application.specification.key",
        tracking=1,
        ondelete="restrict",
        domain="[('id', 'in', allowed_specification_keys)]",
        string="Specification Name",
        required=True,
    )
    name = fields.Char(
        related="key_id.name",
    )
    value = fields.Text(
        tracking=2,
    )
    application_id = fields.Many2one(
        comodel_name="partner.application",
        tracking=1,
        ondelete="cascade",
    )
    allowed_specification_keys = fields.Many2many(
        related="application_id.application_type_id.allowed_specification_keys",
    )

    @api.constrains("key_id")
    def _constrain_key_id(self):
        for rec in self:
            if rec.key_id not in rec.allowed_specification_keys:
                raise ValidationError(
                    _(
                        f"Key '{rec.key_id.name}' is not allowed for this application type."
                    )
                )
