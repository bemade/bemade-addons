from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PartnerApplication(models.Model):
    _inherit = "partner.application"

    equipment_ids = fields.One2many(
        comodel_name="fsm.equipment",
        inverse_name="application_id",
        string="Equipment",
    )
    equipment_count = fields.Integer(
        compute="_compute_equipment_count",
        string="Equipment Count",
    )

    @api.constrains("equipment_ids")
    def _check_equipment_ids(self):
        for application in self:
            if len(application.equipment_ids.partner_id) > 1:
                raise ValidationError(
                    _("An application can only be linked to one partner.")
                )

    @api.depends("equipment_ids")
    def _compute_equipment_count(self):
        for application in self:
            application.equipment_count = len(application.equipment_ids)
