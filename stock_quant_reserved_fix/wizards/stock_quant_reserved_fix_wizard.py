from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockQuantReservedFixWizard(models.TransientModel):
    _name = "stock.quant.reserved.fix.wizard"
    _description = "Stock Quant Reserved Quantity Fix Wizard"

    quant_ids = fields.Many2many(
        "stock.quant",
        string="Stock Quants",
        required=True,
        help="Stock quants to update reserved quantity for",
    )

    reserved_quantity = fields.Float(
        string="New Reserved Quantity",
        digits="Product Unit of Measure",
        required=True,
        help="The new reserved quantity to set for the selected stock quants",
    )

    quant_count = fields.Integer(
        string="Number of Quants",
        compute="_compute_quant_count",
        help="Number of selected stock quants",
    )

    @api.depends("quant_ids")
    def _compute_quant_count(self):
        for wizard in self:
            wizard.quant_count = len(wizard.quant_ids)

    @api.model
    def default_get(self, fields_list):
        """Get default values from context"""
        res = super().default_get(fields_list)

        # Get active stock quant records from context
        active_ids = self.env.context.get("active_ids", [])
        active_model = self.env.context.get("active_model")

        if active_model == "stock.quant" and active_ids:
            res["quant_ids"] = [(6, 0, active_ids)]
            res["reserved_quantity"] = 0

        return res

    def action_fix_reserved_quantity(self):
        """Update the reserved quantity for selected stock quants"""
        if not self.quant_ids:
            raise UserError(_("No stock quants selected."))

        if self.reserved_quantity < 0:
            raise UserError(_("Reserved quantity cannot be negative."))

        # Check if user has write access to stock.quant
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("You need to be a Stock Manager to perform this action."))

        # Update reserved quantity for all selected quants
        updated_count = 0
        for quant in self.quant_ids:
            # Validate that the reserved quantity doesn't exceed available quantity
            if self.reserved_quantity > quant.quantity:
                raise UserError(
                    _(
                        "Reserved quantity (%.2f) cannot exceed available quantity (%.2f) "
                        "for product %s in location %s."
                    )
                    % (
                        self.reserved_quantity,
                        quant.quantity,
                        quant.product_id.display_name,
                        quant.location_id.display_name,
                    )
                )

            # Update the reserved quantity
            quant.sudo().write({"reserved_quantity": self.reserved_quantity})
            updated_count += 1

        # Show success message
        message = _(
            "Successfully updated reserved quantity to %.2f for %d stock quant(s)."
        ) % (self.reserved_quantity, updated_count)

        # Close the wizard and show success notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
