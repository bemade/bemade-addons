from odoo import models, fields, api


class EquipmentComponent(models.Model):
    _name = "fsm.equipment.component"
    _description = "Equipment Component"

    sequence = fields.Integer()
    name = fields.Char()
    product_id = fields.Many2one(
        "product.product",
        ondelete="cascade",
    )
    purpose_id = fields.Many2one(
        "fsm.equipment.component.purpose",
        ondelete="restrict",
    )
    equipment_id = fields.Many2one(
        "fsm.equipment",
        ondelete="cascade",
    )
    note = fields.Text()

    @api.onchange("product_id")
    def onchange_product_id(self):
        for rec in self:
            rec.name = rec.product_id.display_name


class EquipmentComponentPurpose(models.Model):
    _name = "fsm.equipment.component.purpose"
    _description = "Component Purpose"

    name = fields.Char(translate=True)
