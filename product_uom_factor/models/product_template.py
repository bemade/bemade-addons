# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    uom_factor_ids = fields.One2many(
        "product.uom.factor",
        "product_tmpl_id",
        string="UoM Conversion Factors",
    )

    def write(self, vals):
        res = super().write(vals)
        if "uom_factor_ids" in vals or "uom_ids" in vals:
            self._sync_factor_uom_ids()
        return res

    def _sync_factor_uom_ids(self):
        """Additive sync: ensure each factor's delegate_uom_id is in uom_ids.

        NEVER removes a generic unit from uom_ids. NEVER swaps. Only adds.
        This fixes the 'factor disappears on save' bug from the old clone-swap.
        """
        for template in self:
            factor_uoms = template.uom_factor_ids.mapped("delegate_uom_id")
            existing_uoms = template.uom_ids
            missing = factor_uoms - existing_uoms
            if missing:
                template.uom_ids = [fields.Command.link(uom.id) for uom in missing]

    @api.constrains("uom_id", "uom_factor_ids")
    def _check_base_uom_change(self):
        """Block base UoM change while factor rows exist.

        Changing uom_id would orphan existing factor rows whose delegate
        has relative_uom_id pointing to the old base UoM.
        """
        for template in self:
            if template.uom_factor_ids:
                for factor in template.uom_factor_ids:
                    if (
                        factor.delegate_uom_id
                        and factor.delegate_uom_id.relative_uom_id != template.uom_id
                    ):
                        raise ValidationError(
                            template.env._(
                                "Cannot change the base Unit of Measure while "
                                "product-specific conversion factors exist. Remove "
                                "all UoM conversion factors first, then change the "
                                "base UoM."
                            )
                        )

