# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import fields, models


class PackageFormatOpenWizard(models.TransientModel):
    _name = "stock.package.format.open.wizard"
    _description = "Open packages"

    package_ids = fields.Many2many("stock.package", string="Packages", required=True)
    reason = fields.Char(required=True)

    def action_confirm(self):
        self.ensure_one()
        self.package_ids._package_format_open(self.reason)
        move_ids = self.env.context.get("package_format_assign_move_ids")
        if move_ids:
            moves = self.env["stock.move"].browse(move_ids).exists()
            moves.filtered(
                lambda m: m.state in ("confirmed", "partially_available", "waiting")
            )._action_assign()
        return {"type": "ir.actions.act_window_close"}
