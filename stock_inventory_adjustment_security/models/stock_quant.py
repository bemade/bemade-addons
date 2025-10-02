# -*- coding: utf-8 -*-

from odoo import models, _, api
from odoo.exceptions import AccessError


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _check_inventory_adjustment_permission(self):
        """
        Check if the current user has permission to make inventory adjustments.

        Raises AccessError if the user lacks the required group.
        """
        if not self.env.user.has_group(
            "stock_inventory_adjustment_security.group_inventory_manual_adjustments"
        ):
            raise AccessError(
                _(
                    "You don't have permission to apply inventory adjustments. "
                    "You can count inventory, but only authorized users can apply the changes. "
                    "Please contact your inventory manager."
                )
            )

    def action_apply_inventory(self):
        """
        Override action_apply_inventory to restrict who can apply adjustments.

        This is the main entry point for applying manual inventory adjustments.
        Regular users can count, but only privileged users can apply.
        """
        self._check_inventory_adjustment_permission()
        return super().action_apply_inventory()

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create to restrict quant creation in inventory mode.

        Regular users should not be able to create new quants in inventory mode
        as this is another way to manipulate inventory levels.
        """
        if self._is_inventory_mode():
            self._check_inventory_adjustment_permission()

        return super().create(vals_list)

    def write(self, vals):
        """
        Override write to restrict quantity changes in inventory mode.

        This catches direct quantity modifications during inventory adjustments.
        Automatic operations (pickings, manufacturing, etc.) don't set
        inventory_mode context, so they are unaffected.
        """
        if self._is_inventory_mode() and "quantity" in vals:
            self._check_inventory_adjustment_permission()

        return super().write(vals)
