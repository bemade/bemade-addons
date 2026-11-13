# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import api, fields, models
from odoo.exceptions import UserError

from ..models.product import bilingual


class PackageFormatRepackWizard(models.TransientModel):
    _name = "stock.package.format.repack.wizard"
    _description = "Repack stock into another package format"

    product_id = fields.Many2one(
        "product.product", required=True, domain=[("uses_package_rule", "=", True)]
    )
    location_id = fields.Many2one(
        "stock.location", required=True, domain=[("usage", "=", "internal")]
    )
    source_package_id = fields.Many2one(
        "stock.package",
        string="From package",
        help="Leave empty to repack loose stock. An unopened package is opened "
        "(and logged) by the repack.",
    )
    lot_id = fields.Many2one(
        "stock.lot", required=True, domain="[('product_id', '=', product_id)]"
    )
    allowed_format_ids = fields.Many2many("uom.uom", compute="_compute_allowed_format_ids")
    format_uom_id = fields.Many2one(
        "uom.uom", string="Into format", required=True,
        domain="[('id', 'in', allowed_format_ids)]",
    )
    package_count = fields.Integer("New packages", default=1, required=True)
    quantity = fields.Float(compute="_compute_quantity", digits="Product Unit")
    reason = fields.Char(required=True)

    @api.depends("product_id")
    def _compute_allowed_format_ids(self):
        for wizard in self:
            wizard.allowed_format_ids = (
                wizard.product_id._package_format_uoms() if wizard.product_id else False
            )

    @api.depends("format_uom_id", "package_count", "product_id")
    def _compute_quantity(self):
        for wizard in self:
            wizard.quantity = (
                wizard.package_count * wizard.product_id._package_format_size(wizard.format_uom_id)
                if wizard.product_id and wizard.format_uom_id
                else 0.0
            )

    def _source_quants(self):
        return self.env["stock.quant"].sudo().search(
            [
                ("product_id", "=", self.product_id.id),
                ("location_id", "=", self.location_id.id),
                ("lot_id", "=", self.lot_id.id),
                ("package_id", "=", self.source_package_id.id or False),
                ("quantity", ">", 0),
            ]
        )

    def action_confirm(self):
        self.action_confirm_packages()
        return {"type": "ir.actions.act_window_close"}

    def action_confirm_packages(self):
        """Repack and return the new packages."""
        self.ensure_one()
        self.env["stock.package"]._package_format_check_open_right()
        product = self.product_id
        if self.format_uom_id not in product._package_format_uoms():
            raise UserError(self.env._("Choose one of the product's formats."))
        if self.package_count <= 0:
            raise UserError(self.env._("The number of new packages must be positive."))
        size = product._package_format_size(self.format_uom_id)
        need = self.package_count * size
        quants = self._source_quants()
        free = sum(q.quantity - q.reserved_quantity for q in quants)
        if product.uom_id.compare(need, free) > 0:
            raise UserError(
                self.env._(
                    "Only %(free)s %(uom)s of lot %(lot)s are free in %(origin)s; "
                    "%(need)s %(uom)s are needed. A repack takes one lot at a time.",
                    free=product._package_format_qty_str(free),
                    need=product._package_format_qty_str(need),
                    uom=product.uom_id.name,
                    lot=self.lot_id.name,
                    origin=self.source_package_id.name or self.location_id.display_name,
                )
            )
        source = self.source_package_id
        if source and not source.is_opened:
            source._package_format_open(self.reason)
        new_packages = self.env["stock.package"].create(
            [{"package_type_id": self.format_uom_id.package_type_id.id}] * self.package_count
        )
        move = (
            self.env["stock.move"]
            .sudo()
            .create(
                {
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": need,
                    "location_id": self.location_id.id,
                    "location_dest_id": self.location_id.id,
                    "company_id": self.location_id.company_id.id or self.env.company.id,
                    "origin": self.env._("Repack: %(reason)s", reason=self.reason),
                }
            )
        )
        move._action_confirm()
        self.env["stock.move.line"].sudo().create(
            [
                {
                    "move_id": move.id,
                    "product_id": product.id,
                    "product_uom_id": product.uom_id.id,
                    "quantity": size,
                    "location_id": self.location_id.id,
                    "location_dest_id": self.location_id.id,
                    "lot_id": self.lot_id.id,
                    "package_id": source.id or False,
                    "result_package_id": package.id,
                    "picked": True,
                }
                for package in new_packages
            ]
        )
        move.picked = True
        move._action_done()
        user_name = self.env.user.name
        source_name = source.name or self.location_id.display_name
        reason = self.reason
        for package in new_packages:
            package.sudo().message_post(
                body=bilingual(
                    self.env,
                    lambda env: env._(
                        "Repacked from %(origin)s by %(user)s. Reason: %(reason)s",
                        origin=source_name,
                        user=user_name,
                        reason=reason,
                    ),
                )
            )
        if source:
            fmt_name = self.format_uom_id.package_type_id.name
            count = self.package_count
            source.sudo().message_post(
                body=bilingual(
                    self.env,
                    lambda env: env._(
                        "%(count)s × %(type)s repacked from this package by %(user)s.",
                        count=count,
                        type=fmt_name,
                        user=user_name,
                    ),
                )
            )
        return new_packages
