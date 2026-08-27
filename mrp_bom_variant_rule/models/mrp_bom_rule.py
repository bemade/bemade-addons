# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools.expression import check_expression, evaluate_expression


class MrpBomRule(models.Model):
    _name = "mrp.bom.rule"
    _description = "BOM generation rule"
    _order = "slot_id, sequence, id"

    rule_set_id = fields.Many2one(
        comodel_name="mrp.bom.rule.set",
        string="Ruleset",
        related="slot_id.rule_set_id",
        store=True,
        index=True,
    )
    slot_id = fields.Many2one(
        comodel_name="mrp.bom.slot",
        string="Slot",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    condition_ids = fields.One2many(
        comodel_name="mrp.bom.rule.condition",
        inverse_name="rule_id",
        string="Conditions",
        help="All conditions must hold for the rule to match. A rule with no "
        "conditions matches every variant and is therefore a catch-all.",
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Component",
        required=True,
        ondelete="restrict",
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Unit of Measure",
        help="Defaults to the component's own unit of measure.",
    )
    qty_expr = fields.Char(
        string="Quantity",
        required=True,
        default="1",
        help="Arithmetic over the variant's named parameters, "
        "for example 'volume * 1.2 * trains'.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        rules.rule_set_id._bump_revision()
        return rules

    def write(self, vals):
        # The ruleset the rule belonged to before the write has also changed
        # shape, so both sides of a re-parenting move.
        rule_sets = self.rule_set_id
        result = super().write(vals)
        (rule_sets | self.rule_set_id)._bump_revision()
        return result

    def unlink(self):
        rule_sets = self.rule_set_id
        result = super().unlink()
        rule_sets.exists()._bump_revision()
        return result

    @api.constrains("qty_expr")
    def _check_qty_expr(self):
        for rule in self:
            try:
                check_expression(rule.qty_expr)
            except ValueError as err:
                raise ValidationError(
                    _(
                        "Quantity expression %(expr)r is not a valid "
                        "arithmetic expression: %(reason)s",
                        expr=rule.qty_expr,
                        reason=str(err),
                    )
                ) from err

    def _matches(self, variant):
        """True when every condition of this rule holds for the variant."""
        self.ensure_one()
        values = variant.product_template_attribute_value_ids.mapped(
            "product_attribute_value_id"
        )
        return all(
            condition._holds(values) for condition in self.condition_ids
        )

    def _compute_qty(self, params):
        """Quantity this rule contributes, given the variant's parameters."""
        self.ensure_one()
        return evaluate_expression(self.qty_expr, params)


class MrpBomRuleCondition(models.Model):
    _name = "mrp.bom.rule.condition"
    _description = "Attribute condition of a BOM generation rule"
    _order = "rule_id, id"

    rule_id = fields.Many2one(
        comodel_name="mrp.bom.rule",
        string="Rule",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attribute_id = fields.Many2one(
        comodel_name="product.attribute",
        string="Attribute",
        required=True,
        ondelete="cascade",
    )
    value_ids = fields.Many2many(
        comodel_name="product.attribute.value",
        string="Values",
        required=True,
        help="The condition holds when the variant carries any one of these "
        "values for the attribute.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        conditions = super().create(vals_list)
        conditions.rule_id.rule_set_id._bump_revision()
        return conditions

    def write(self, vals):
        result = super().write(vals)
        self.rule_id.rule_set_id._bump_revision()
        return result

    def unlink(self):
        rule_sets = self.rule_id.rule_set_id
        result = super().unlink()
        rule_sets.exists()._bump_revision()
        return result

    def _holds(self, variant_values):
        """A disjunction within one attribute: the variant's value for this
        attribute must be among those listed."""
        self.ensure_one()
        return bool(self.value_ids & variant_values)
