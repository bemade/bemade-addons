# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    package_format_to_pack = fields.Boolean(
        compute="_compute_package_format_to_pack",
        help="Some lines of products stocked in package formats arrive "
        "without packages.",
    )

    @api.depends("move_ids.move_line_ids.result_package_id", "move_ids.state", "state")
    def _compute_package_format_to_pack(self):
        for picking in self:
            picking.package_format_to_pack = bool(picking._package_format_moves_to_pack())

    def _package_format_moves_to_pack(self):
        """Moves bringing a flagged product into stock from outside the
        warehouse (vendor, customer return...) with unpacked quantities."""
        return self.move_ids.filtered(
            lambda m: m.state not in ("done", "cancel")
            and m.product_id.uses_package_rule
            and m.location_dest_id.usage == "internal"
            and m.location_id.usage not in ("internal", "transit")
            and m._package_format_unpacked_qty() > 0
        )

    def button_validate(self):
        if not self.env.context.get("package_format_skip_pack"):
            moves = self.filtered(lambda p: p.state != "done")._package_format_moves_to_pack()
            if moves:
                return self.env["stock.package.format.pack.wizard"]._open_for_moves(
                    self, moves, validate=True
                )
        return super().button_validate()

    def action_package_format_pack(self):
        moves = self._package_format_moves_to_pack()
        if not moves:
            return False
        return self.env["stock.package.format.pack.wizard"]._open_for_moves(
            self, moves, validate=False
        )

    def _action_done(self):
        # Whole packages reserved by any path (custom re-reservation code
        # included) travel as packages.
        flagged = self.filtered(
            lambda p: any(p.move_line_ids.product_id.mapped("uses_package_rule"))
        )
        if flagged:
            flagged._check_entire_pack()
        return super()._action_done()
