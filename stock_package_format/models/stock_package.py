# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import fields, models
from odoo.exceptions import AccessError

from .product import bilingual

OPEN_GROUP = "stock_package_format.group_package_open"


class StockPackage(models.Model):
    _name = "stock.package"
    _inherit = ["stock.package", "mail.thread"]

    is_opened = fields.Boolean(
        "Opened",
        copy=False,
        index=True,
        help="An opened package may be taken from in any quantity. Unopened "
        "packages are only reserved and moved whole.",
    )
    opened_by_id = fields.Many2one("res.users", "Opened by", copy=False, readonly=True)
    opened_date = fields.Datetime("Opened on", copy=False, readonly=True)
    open_reason = fields.Char("Reason for opening", copy=False, readonly=True)

    def _package_format_check_open_right(self):
        if not self.env.user.has_group(OPEN_GROUP):
            raise AccessError(
                self.env._(
                    "Only users of the « Can open packages » group may open or "
                    "repack packages."
                )
            )

    def _package_format_open(self, reason):
        """Open the packages: flag, stamp who/when/why and log it."""
        self._package_format_check_open_right()
        to_open = self.filtered(lambda p: not p.is_opened)
        now = fields.Datetime.now()
        to_open.sudo().write(
            {
                "is_opened": True,
                "opened_by_id": self.env.user.id,
                "opened_date": now,
                "open_reason": reason,
            }
        )
        user_name = self.env.user.name
        for package in to_open:
            body = bilingual(
                self.env,
                lambda env: env._(
                    "Package opened by %(user)s. Reason: %(reason)s",
                    user=user_name,
                    reason=reason,
                ),
            )
            package.sudo().message_post(body=body)
        return True

    def action_package_format_open(self):
        self._package_format_check_open_right()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Open packages"),
            "res_model": "stock.package.format.open.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_package_ids": self.ids},
        }

    def action_package_format_repack(self):
        self.ensure_one()
        self._package_format_check_open_right()
        quant = self.quant_ids.filtered(lambda q: q.quantity > 0)[:1]
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Repack"),
            "res_model": "stock.package.format.repack.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_source_package_id": self.id,
                "default_product_id": quant.product_id.id,
                "default_location_id": self.location_id.id,
                "default_lot_id": quant.lot_id.id,
            },
        }
