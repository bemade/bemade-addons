from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_is_zero, float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    purchase_price_vendor = fields.Float(
        compute="_compute_purchase_price_vendor",
        string="Vendor Price",
        groups="base.group_user",
        digits="Product Price",
    )

    purchase_price_actual = fields.Float(
        compute="_compute_actual_gp",
        digits="Product Price",
        groups="base.group_user",
        string="Purchase Price",
    )

    gross_profit = fields.Float(
        compute="_compute_actual_gp",
        digits="Product Price",
        groups="base.group_user",
    )

    gross_profit_percent = fields.Float(
        compute="_compute_actual_gp",
        groups="base.group_user",
        string="Gross Profit (%)",
    )

    @api.depends(
        "purchase_price",
        "purchase_price_vendor",
        "product_id",
        "product_uom_id",
        "product_uom_qty",
        "order_id.warehouse_id",
        "move_ids.state",
        "move_ids.quantity",
        "qty_to_deliver",
    )
    def _compute_actual_gp(self):
        """We want to use the gross profit based on average inventory valuation when the
        sale order line will be completely fulfilled (or has been fulfilled) from stock.
        For product not yet in stock we want to use the vendor price. We can also have
        blended calculations (partly on vendor price, partly on stock valuation). This
        occurs when an order has been or would be partially fulfilled from available
        stock.
        :return:
        """
        non_product_lines = self.filtered(lambda r: not r.product_id)
        non_product_lines.purchase_price_actual = 0.0
        non_product_lines.gross_profit = 0.0
        non_product_lines.gross_profit_percent = 0.0
        product_lines = self - non_product_lines
        coverage = product_lines._margin_stock_coverage()
        for line in product_lines:
            stock_missing = line._margin_missing_from_coverage(coverage)
            # the UoM can be blank while the line is being edited (onchange)
            rounding = (
                line.product_uom_id.rounding
                or line.product_id.uom_id.rounding
                or 0.01
            )
            if float_is_zero(stock_missing, precision_rounding=rounding):
                # everything is coming from stock, use inventory valuation
                line.purchase_price_actual = line.purchase_price
            elif (
                float_compare(
                    line.product_uom_qty,
                    stock_missing,
                    precision_rounding=rounding,
                )
                <= 0
            ):
                # everything is coming from the vendor, use vendor pricing
                line.purchase_price_actual = line.purchase_price_vendor
            else:
                # we have a mix, use blended pricing
                qty_from_stock = line.product_uom_qty - stock_missing
                line.purchase_price_actual = (
                    (
                        stock_missing * line.purchase_price_vendor
                        + qty_from_stock * line.purchase_price
                    )
                    / line.product_uom_qty
                    if line.product_uom_qty != 0
                    else 0
                )
            line.gross_profit = line.price_subtotal - (
                line.purchase_price_actual * line.product_uom_qty
            )
            line.gross_profit_percent = (
                line.price_subtotal and line.gross_profit / line.price_subtotal
                if line.price_subtotal != 0
                else 0
            )

    def _determine_missing_stock(self) -> float:
        """Compute how much stock is missing to meet an order line's demand.  In the
        case of a quotation line, available stock is checked as if the order were to be
        placed immediately.

        Thin per-line wrapper around :meth:`_margin_stock_coverage`, kept for callers
        and overrides.

        :return: The quantity missing from free stock to fulfill the line, in
        the unit of measure of the line (``product_uom_id``).
        """
        self.ensure_one()
        return self._margin_missing_from_coverage(self._margin_stock_coverage())

    def _margin_line_uom(self):
        self.ensure_one()
        return self.product_uom_id or self.product_id.uom_id

    def _margin_to_product_uom(self, qty):
        self.ensure_one()
        uom = self._margin_line_uom()
        product_uom = self.product_id.uom_id
        if not uom or uom == product_uom:
            return qty
        return uom._compute_quantity(qty, product_uom, round=False)

    def _margin_from_product_uom(self, qty):
        self.ensure_one()
        uom = self._margin_line_uom()
        product_uom = self.product_id.uom_id
        if not uom or uom == product_uom:
            return qty
        return product_uom._compute_quantity(qty, uom, round=False)

    def _margin_needed_qty(self):
        """``(needed, own_reserved)`` in the product's UoM.

        Quotation: the ordered quantity, nothing reserved. Confirmed order: what is
        left to deliver, and what is already reserved on the line's own open
        outgoing moves (capped at what is left).
        """
        self.ensure_one()
        if self.order_id.state != "sale":
            return max(self._margin_to_product_uom(self.product_uom_qty), 0.0), 0.0
        needed = max(self._margin_to_product_uom(self.qty_to_deliver), 0.0)
        if not needed:
            return 0.0, 0.0
        product_uom = self.product_id.uom_id
        reserved = 0.0
        for move in self.move_ids:
            if (
                move.state in ("done", "cancel")
                or move.location_dest_id.usage != "customer"
                or move.location_id.usage != "internal"
            ):
                continue
            reserved += move.product_uom._compute_quantity(
                move.quantity, product_uom, round=False
            )
        return needed, min(max(reserved, 0.0), needed)

    def _margin_stock_coverage(self):
        """``{line id: qty covered by stock}``, in the product's UoM.

        Shared rule (kept in step with ``sale_cost_source``'s
        ``_cost_source_stock_coverage``): stock is the **free** quantity
        (``free_qty``, net of reservations) in each order's warehouse, read in one
        batch per warehouse. Lines of the same product on the same order draw on
        that free stock in sequence, so two lines of 6 against 10 in stock see 6
        and 4, not 6 and 6. All product lines of the orders involved are taken
        into account, so reading one line alone gives the same answer as reading
        the whole order.

        On a confirmed order, the quantity already reserved on a line's own
        outgoing moves counts as covered (it is no longer free stock), and only
        the rest draws on the free stock.
        """
        lines = self.filtered("product_id")
        lines |= lines.order_id.order_line.filtered("product_id")
        coverage = {}
        by_warehouse = defaultdict(list)
        for order in lines.order_id:
            by_warehouse[order.warehouse_id].append(order)
        wanted = set(lines._ids)
        seen = set()
        for warehouse, orders in by_warehouse.items():
            order_lines = [
                line
                for order in orders
                for line in order.order_line
                if line.id in wanted
            ]
            # lines of self not (yet) in their order's order_line (onchange)
            listed = {line.id for line in order_lines}
            order_lines += [
                line
                for line in lines
                if line.order_id in orders and line.id not in listed
            ]
            products = self.env["product.product"].union(
                *(line.product_id for line in order_lines)
            )
            products = products.with_context(warehouse_id=warehouse.id or False)
            free = {product.id: max(product.free_qty, 0.0) for product in products}
            remaining = defaultdict(dict)
            for line in order_lines:
                if line.id in seen:
                    continue
                seen.add(line.id)
                needed, own_reserved = line._margin_needed_qty()
                pool = remaining[line.order_id.id]
                available = pool.setdefault(
                    line.product_id.id, free.get(line.product_id.id, 0.0)
                )
                covered = min(available, needed - own_reserved)
                pool[line.product_id.id] = available - covered
                coverage[line.id] = own_reserved + covered
        return coverage

    def _margin_missing_from_coverage(self, coverage):
        """Quantity missing from stock, in the line's UoM, given ``coverage``."""
        self.ensure_one()
        needed, _own_reserved = self._margin_needed_qty()
        missing = max(needed - coverage.get(self.id, 0.0), 0.0)
        return self._margin_from_product_uom(missing)

    @api.depends("product_id", "product_id.seller_ids", "product_id.seller_ids.price")
    def _compute_purchase_price_vendor(self):
        for line in self:
            product = line.product_id
            suppinfos = product.seller_ids.sorted("sequence")
            if not suppinfos:
                line.purchase_price_vendor = 0.0
                continue
            suppinfo = suppinfos[0]
            purch_currency = suppinfo.currency_id
            to_cur = line.currency_id or line.order_id.currency_id
            line.purchase_price_vendor = (
                purch_currency._convert(
                    from_amount=suppinfo.price,
                    to_currency=to_cur,
                    company=line.company_id or self.env.company,
                    date=line.order_id.date_order or fields.Date.today(),
                    round=False,
                )
                if to_cur and suppinfo.price
                else suppinfo.price
            )
