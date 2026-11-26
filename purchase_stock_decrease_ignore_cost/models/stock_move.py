# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import api, models
from odoo.tools.float_utils import float_compare


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model
    def _prepare_merge_negative_moves_excluded_distinct_fields(self):
        excluded = super()._prepare_merge_negative_moves_excluded_distinct_fields()
        if self.env.context.get("purchase_decrease_ignore_cost"):
            excluded.append("price_unit")
        return excluded

    def _merge_moves(self, merge_into=False):
        """Let a purchase line decrease absorb its open receipt moves whatever
        their cost, and keep each move's own cost.

        Odoo only nets a negative move against a positive one with the same
        ``price_unit``. On a foreign-currency order, the decrease is converted
        at the rate loaded when the quantity is changed, so a new rate turns
        the decrease into a return to the vendor. Odoo's netting also replaces
        the remaining move's cost with a weighted average of both costs; that
        average is meaningless here, so the original costs are put back.
        """
        negative_moves = self.filtered(
            lambda m: float_compare(
                m.product_uom_qty, 0, precision_rounding=m.product_uom.rounding
            )
            < 0
        )
        if not negative_moves or not all(
            m.purchase_line_id and m.company_id.purchase_decrease_ignore_cost
            for m in negative_moves
        ):
            return super()._merge_moves(merge_into=merge_into)

        moves_to_restore = negative_moves | negative_moves.purchase_line_id.move_ids
        original_costs = {move.id: move.price_unit for move in moves_to_restore}
        merged = super(
            StockMove, self.with_context(purchase_decrease_ignore_cost=True)
        )._merge_moves(merge_into=merge_into)
        for move in moves_to_restore.exists():
            if move.state != "cancel" and move.price_unit != original_costs[move.id]:
                move.price_unit = original_costs[move.id]
        return merged.with_env(self.env)
