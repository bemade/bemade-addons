# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import api, fields, models


class MrpBomSlot(models.Model):
    _name = "mrp.bom.slot"
    _description = "Component slot of a BOM ruleset"
    _order = "rule_set_id, sequence, id"

    rule_set_id = fields.Many2one(
        comodel_name="mrp.bom.rule.set",
        string="Ruleset",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    required = fields.Boolean(
        default=True,
        help="A required slot that matches no rule refuses generation "
        "outright. Clear this for slots a configuration may legitimately "
        "leave empty.",
    )
    rule_ids = fields.One2many(
        comodel_name="mrp.bom.rule",
        inverse_name="slot_id",
        string="Rules",
    )

    @api.model_create_multi
    def create(self, vals_list):
        slots = super().create(vals_list)
        slots.rule_set_id._bump_revision()
        return slots

    def write(self, vals):
        rule_sets = self.rule_set_id
        result = super().write(vals)
        (rule_sets | self.rule_set_id)._bump_revision()
        return result

    def unlink(self):
        rule_sets = self.rule_set_id
        result = super().unlink()
        rule_sets.exists()._bump_revision()
        return result
