# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    package_format_proposal_ids = fields.Many2many(
        "stock.package",
        string="Packages to open",
        compute="_compute_package_format_proposal",
        help="Unopened packages that would cover what this move still misses "
        "(moves in the base unit only take loose stock and opened packages).",
    )
    package_format_proposal = fields.Char(
        "Open to cover", compute="_compute_package_format_proposal"
    )

    def _package_format_is_loose(self):
        self.ensure_one()
        product = self.product_id
        return bool(
            product.uses_package_rule
            and not product._package_format_of_uom(self.packaging_uom_id or self.product_uom)
        )

    @api.depends("state", "quantity", "product_uom_qty", "product_id", "location_id")
    def _compute_package_format_proposal(self):
        for move in self:
            packages = self.env["stock.package"]
            if (
                move.state in ("confirmed", "partially_available", "waiting")
                and move.location_id.usage == "internal"
                and move.product_id
                and move._package_format_is_loose()
            ):
                product = move.product_id
                missing = move.product_qty - move.product_uom._compute_quantity(
                    move.quantity, product.uom_id, round=False
                )
                if product.uom_id.compare(missing, 0) > 0:
                    # free loose stock can still be reserved: no need to open for it
                    missing -= product._package_format_loose_free(move.location_id)
                    packages = product._package_format_propose_open(missing, move.location_id)
            move.package_format_proposal_ids = packages
            move.package_format_proposal = (
                packages
                and move.product_id._package_format_describe_packages(packages)
                or False
            )

    def action_package_format_open_proposal(self):
        self.ensure_one()
        action = self.package_format_proposal_ids.action_package_format_open()
        action["context"] = dict(action["context"], package_format_assign_move_ids=self.ids)
        return action

    def _package_format_unpacked_lines(self):
        return self.move_line_ids.filtered(
            lambda ml: not ml.result_package_id and ml.product_uom_id.compare(ml.quantity, 0) > 0
        )

    def _package_format_unpacked_qty(self):
        """Unpacked quantity of the move, in the product unit; the demand when
        nothing is set yet."""
        self.ensure_one()
        lines = self._package_format_unpacked_lines()
        if lines:
            return sum(lines.mapped("quantity_product_uom"))
        if self.move_line_ids or self.product_uom.is_zero(self.product_uom_qty):
            return 0.0
        return self.product_qty
