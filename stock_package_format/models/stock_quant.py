# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import api, fields, models
from odoo.fields import Domain


class StockQuant(models.Model):
    _inherit = "stock.quant"

    package_type_id = fields.Many2one(
        related="package_id.package_type_id", store=True, string="Package Type"
    )
    package_is_opened = fields.Boolean(
        related="package_id.is_opened", store=True, string="Package opened"
    )

    def _get_gather_domain(
        self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False
    ):
        domain = super()._get_gather_domain(
            product_id, location_id, lot_id, package_id, owner_id, strict
        )
        if self.env.context.get("package_format_loose") == product_id.id and not package_id:
            # Loose moves only see loose stock and opened packages.
            domain = Domain.AND(
                [
                    domain,
                    Domain("package_id", "=", False) | Domain("package_id.is_opened", "=", True),
                ]
            )
        return domain

    @api.model
    def _get_reserve_quantity(
        self,
        product_id,
        location_id,
        quantity,
        uom_id=None,
        lot_id=None,
        package_id=None,
        owner_id=None,
        strict=False,
    ):
        if (
            not product_id.uses_package_rule
            or package_id
            or product_id.uom_id.compare(quantity, 0) <= 0
            or self.env.context.get("package_format_bypass")
        ):
            return super()._get_reserve_quantity(
                product_id, location_id, quantity, uom_id=uom_id, lot_id=lot_id,
                package_id=package_id, owner_id=owner_id, strict=strict,
            )
        fmt = product_id._package_format_of_uom(self.env.context.get("packaging_uom_id"))
        if not fmt:
            # Loose need: loose stock and opened packages only.
            return super(
                StockQuant, self.with_context(package_format_loose=product_id.id)
            )._get_reserve_quantity(
                product_id, location_id, quantity, uom_id=uom_id, lot_id=lot_id,
                package_id=package_id, owner_id=owner_id, strict=strict,
            )
        return self._package_format_whole_packages(
            product_id, location_id, quantity, fmt, lot_id=lot_id, owner_id=owner_id,
            strict=strict,
        )

    @api.model
    def _package_format_whole_packages(
        self, product, location, quantity, fmt, lot_id=None, owner_id=None, strict=False
    ):
        """Pick unopened, entirely free packages of format ``fmt`` whose content
        fits in ``quantity``; return [(quant, quantity)] as core does."""
        quants = self.sudo()._gather(
            product, location, lot_id=lot_id, owner_id=owner_id, strict=False
        )
        packages = []
        content = {}
        for quant in quants:
            package = quant.package_id
            if strict and quant.location_id != location:
                continue
            if (
                not package
                or package.is_opened
                or package.package_type_id != fmt.package_type_id
            ):
                continue
            if package not in content:
                packages.append(package)
                content[package] = self.browse()
            content[package] |= quant
        uom = product.uom_id
        result = []
        remaining = quantity
        for package in packages:
            pquants = content[package]
            # The whole package must be free: no reservation on any of its
            # quants of this product (wherever gathered from).
            all_quants = package.quant_ids.filtered(lambda q, p=product: q.product_id == p)
            if any(uom.compare(q.reserved_quantity, 0) != 0 for q in all_quants):
                continue
            if any(uom.compare(q.quantity, 0) < 0 for q in all_quants):
                continue
            total = sum(pquants.mapped("quantity"))
            if uom.compare(total, 0) <= 0 or uom.compare(total, remaining) > 0:
                continue
            for quant in pquants:
                result.append((quant, quant.quantity))
            remaining -= total
            if uom.is_zero(remaining):
                break
        return result
