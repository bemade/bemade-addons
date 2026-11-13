# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from collections import defaultdict

from odoo import models
from odoo.exceptions import UserError


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    def _package_format_check_no_split(self):
        """Refuse to take part of an unopened package of a flagged product."""
        taken = defaultdict(float)
        for ml in self:
            package = ml.package_id
            if (
                not package
                or package.is_opened
                or ml.is_inventory
                or ml.result_package_id == package
                or not ml.product_id.uses_package_rule
                or ml.product_uom_id.compare(ml.quantity, 0) <= 0
            ):
                continue
            taken[package, ml.product_id, ml.location_id] += ml.quantity_product_uom
        for (package, product, location), qty in taken.items():
            content = sum(
                package.quant_ids.filtered(
                    lambda q, p=product, loc=location: q.product_id == p and q.location_id == loc
                ).mapped("quantity")
            )
            if product.uom_id.compare(qty, content) < 0:
                raise UserError(
                    self.env._(
                        "Package %(package)s of %(product)s is not opened: it can "
                        "only be moved whole (%(content)s %(uom)s, here %(qty)s). "
                        "Open it first, or take the whole package.",
                        package=package.name,
                        product=product.display_name,
                        content=product._package_format_qty_str(content),
                        qty=product._package_format_qty_str(qty),
                        uom=product.uom_id.name,
                    )
                )

    def _action_done(self):
        self._package_format_check_no_split()
        return super()._action_done()
