from odoo import models, fields, api
from odoo.osv import expression


class Partner(models.Model):
    _inherit = "res.partner"

    equipment_count = fields.Integer(compute="_compute_equipment_count")

    owned_equipment_ids = fields.One2many(
        comodel_name="fsm.equipment",
        compute="_compute_owned_equipment_ids",
        string="Owned Equipments",
    )

    equipment_ids = fields.One2many(
        comodel_name="fsm.equipment",
        inverse_name="partner_id",
        string="Site Equipment",
    )

    is_service_site = fields.Boolean(
        compute="_compute_is_service_site",
        help="A partner is a service site if it has one or more equipments.",
        store=True,
        compute_sudo=True,
    )

    @api.depends(
        "equipment_ids",
        "child_ids",
        "child_ids.company_type",
        "child_ids.equipment_ids",
    )
    def _compute_owned_equipment_ids(self):
        for rec in self:
            ids = rec.equipment_ids | rec.child_ids.mapped("equipment_ids")
            rec.owned_equipment_ids = ids or False

    @api.depends("equipment_ids")
    def _compute_equipment_count(self):
        for rec in self:
            all_equipment_ids = self.env["fsm.equipment"].search(
                [("partner_id", "=", rec.id), ("parent_id", "=", False)]
            )
            rec.equipment_count = len(all_equipment_ids)

    @api.depends("equipment_ids")
    def _compute_is_service_site(self):
        for rec in self:
            rec.is_service_site = bool(rec.equipment_ids)
