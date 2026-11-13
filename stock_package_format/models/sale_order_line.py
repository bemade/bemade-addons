# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.stock.models.stock_rule import ProcurementException

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    package_format_free_count = fields.Integer(
        "Free packages", compute="_compute_package_format_availability"
    )
    package_format_to_buy = fields.Integer(
        "Packages to buy", compute="_compute_package_format_availability"
    )
    package_format_availability = fields.Char(
        "Package availability", compute="_compute_package_format_availability"
    )
    package_format_proposal = fields.Char(
        "Open to cover", compute="_compute_package_format_availability"
    )

    def _package_format_uom(self):
        self.ensure_one()
        if not self.product_id.uses_package_rule:
            return self.env["uom.uom"]
        return self.product_id._package_format_of_uom(self.product_uom_id)

    def _package_format_location(self):
        self.ensure_one()
        return self.order_id.warehouse_id.lot_stock_id

    @api.depends(
        "product_id", "product_uom_id", "product_uom_qty", "order_id.warehouse_id", "state"
    )
    def _compute_package_format_availability(self):
        pools = {}
        for line in self:
            line.package_format_free_count = 0
            line.package_format_to_buy = 0
            line.package_format_availability = False
            line.package_format_proposal = False
            product = line.product_id
            location = line.order_id.warehouse_id.lot_stock_id
            if not product.uses_package_rule or not location or line.display_type:
                continue
            fmt = line._package_format_uom()
            if fmt:
                key = (product, fmt, location)
                if key not in pools:
                    pools[key] = len(product._package_format_free_packages(fmt, location))
                free = pools[key]
                line.package_format_free_count = free
                if line.state == "sale":
                    reserved = sum(
                        m.product_uom._compute_quantity(m.quantity, fmt)
                        for m in line.move_ids
                        if m.state not in ("done", "cancel")
                    )
                    line.package_format_availability = self.env._(
                        "%(reserved)s %(format)s reserved", reserved=int(reserved), format=fmt.name
                    )
                    continue
                wanted = int(round(line.product_uom_qty))
                available = min(free, wanted)
                to_buy = wanted - available
                pools[key] = free - available
                line.package_format_to_buy = to_buy
                if to_buy:
                    line.package_format_availability = self.env._(
                        "%(available)s available · %(to_buy)s to buy",
                        available=available,
                        to_buy=to_buy,
                    )
                else:
                    line.package_format_availability = self.env._(
                        "%(available)s available", available=available
                    )
            elif line.state in ("draft", "sent"):
                need = line.product_uom_id._compute_quantity(
                    line.product_uom_qty, product.uom_id, round=False
                ) - product._package_format_loose_free(location)
                if product.uom_id.compare(need, 0) > 0:
                    packages = product._package_format_propose_open(need, location)
                    if packages:
                        line.package_format_proposal = self.env._(
                            "Open %(packages)s to cover this line",
                            packages=product._package_format_describe_packages(packages),
                        )

    def _package_format_buy_plan(self):
        """Packages to buy per line, computed before confirmation (free
        packages are shared between the lines in order)."""
        plan = {}
        lines = self.sorted(lambda l: (l.order_id.id, l.sequence, l.id))
        lines._compute_package_format_availability()
        for line in lines:
            if line.state not in ("draft", "sent") or line.display_type:
                continue
            fmt = line._package_format_uom()
            if not fmt or line.is_mto:
                continue
            if line.package_format_to_buy > 0:
                plan[line] = (fmt, line.package_format_to_buy)
        return plan

    def _package_format_buy(self, plan):
        """Buy to order: one RFQ line per sale line, in the format unit."""
        Procurement = self.env["stock.rule"].Procurement
        for line, (fmt, count) in plan.items():
            moves = line.move_ids.filtered(lambda m: m.state != "cancel")
            # Multi-step deliveries chain the customer move to a pick move
            # (make_to_order inside the warehouse): only a real MTO route
            # (``is_mto``, filtered by the plan) or a dropship skips the buy.
            if not moves or any(m.location_id.usage == "supplier" for m in moves):
                continue
            warehouse = line.order_id.warehouse_id
            location = warehouse.lot_stock_id
            buy_route = self.env.ref("purchase_stock.route_warehouse0_buy", raise_if_not_found=False)
            values = {
                "warehouse_id": warehouse,
                "route_ids": buy_route or self.env["stock.route"],
                "date_planned": moves[:1].date or fields.Datetime.now(),
                "date_deadline": False,
                "sale_line_id": line.id,
                "force_uom": True,
                "packaging_uom_id": fmt,
                "reference_ids": moves.reference_ids,
                "company_id": line.company_id,
            }
            procurement = Procurement(
                line.product_id,
                count,
                fmt,
                location,
                line.product_id.display_name,
                line.order_id.name,
                line.company_id,
                values,
            )
            try:
                with self.env.cr.savepoint():
                    self.env["stock.rule"].run([procurement])
            except (UserError, ProcurementException) as error:
                _logger.info("Package format buy-to-order failed for %s: %s", line, error)
                line.order_id.message_post(
                    body=self.env._(
                        "Could not create the purchase of %(count)s × %(format)s of "
                        "%(product)s: %(error)s",
                        count=count,
                        format=fmt.name,
                        product=line.product_id.display_name,
                        error=str(error),
                    )
                )
