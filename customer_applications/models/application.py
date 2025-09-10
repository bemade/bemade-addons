from odoo import models, fields, Command


class Application(models.Model):
    _name = "partner.application"
    _description = "Partner Application"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(tracking=1)
    description = fields.Text(tracking=2)
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        tracking=3,
        copy=False,
    )
    application_type_id = fields.Many2one(
        comodel_name="partner.application.type",
        required=True,
        tracking=4,
        ondelete="restrict",
    )
    specification_ids = fields.One2many(
        comodel_name="partner.application.specification",
        inverse_name="application_id",
        tracking=5,
    )

    def copy(self, default=None):
        self.ensure_one()  # This logic won't work for batches, and it doesn't need to
        default = default or {}
        if "specification_ids" not in default:
            default["specification_ids"] = [
                Command.create(line.copy_data()[0]) for line in self.specification_ids
            ]
        return super().copy(default)
