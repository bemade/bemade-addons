# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from collections import defaultdict

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_amount

SALESMAN = "sales_team.group_sale_salesman"

CONFIDENCE_SELECTION = [
    ("firm", "Firm"),
    ("indicative", "Indicative"),
    ("estimated", "Estimated"),
    ("unknown", "Unknown"),
]


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    cost_source_confidence = fields.Selection(
        CONFIDENCE_SELECTION,
        string="Cost Basis",
        compute="_compute_cost_source",
        groups=SALESMAN,
        help="How far the cost behind this line can be trusted. Not stored: "
        "computed each time with today's prices and stock.",
    )
    cost_source_reason = fields.Char(
        string="Cost Basis Reason",
        compute="_compute_cost_source",
        groups=SALESMAN,
    )
    cost_source_explanation = fields.Json(
        string="Cost Basis Details",
        compute="_compute_cost_source",
        groups=SALESMAN,
    )

    @api.depends(
        "display_type",
        "product_id",
        "product_uom_qty",
        "product_uom_id",
        "company_id",
        "currency_id",
        "order_id.warehouse_id",
        "order_id.commitment_date",
        "order_id.expected_date",
    )
    def _compute_cost_source(self):
        today = fields.Date.context_today(self)
        eligible = self.filtered(lambda line: not line._cost_source_excluded())
        (self - eligible).update(
            {
                "cost_source_confidence": False,
                "cost_source_reason": False,
                "cost_source_explanation": False,
            }
        )
        # Share free stock across ALL eligible lines of the orders involved,
        # not only the lines being computed now: reading one line alone must
        # give the same answer as reading the whole order.
        siblings = eligible | eligible.order_id.order_line.filtered(
            lambda line: not line._cost_source_excluded()
        )
        coverage = siblings._cost_source_stock_coverage()
        labels = dict(
            self._fields["cost_source_confidence"]._description_selection(self.env)
        )
        for line in eligible:
            resolution = line._cost_source_resolve(today, coverage.get(line.id, 0.0))
            sentences = resolution.evidence + resolution.warnings + resolution.notes
            line.cost_source_confidence = resolution.confidence
            line.cost_source_reason = " ".join(sentences)
            line.cost_source_explanation = {
                "level": resolution.confidence,
                "level_label": labels.get(resolution.confidence, ""),
                "title": self.env._("Cost basis"),
                "unit_cost": format_amount(
                    self.env, resolution.unit_cost, line._cost_source_currency()
                )
                if resolution.sources
                else "",
                "evidence": resolution.evidence,
                "warnings": resolution.warnings,
                "notes": resolution.notes,
            }

    def _cost_source_excluded(self):
        """True for lines whose cost is not a purchasing question."""
        self.ensure_one()
        product = self.product_id
        return bool(
            self.display_type
            or not product
            or product.type != "consu"
            or not product.is_storable
            or float_compare(self.product_uom_qty, 0.0, precision_digits=6) <= 0
        )

    def _cost_source_qty(self):
        self.ensure_one()
        return self.product_uom_id._compute_quantity(
            self.product_uom_qty, self.product_id.uom_id
        )

    def _cost_source_stock_coverage(self):
        """``{line id: qty covered by free stock}``, in the product's UoM.

        Free stock is read in each order's warehouse, in one batch per
        warehouse. Lines of the same product on the same order draw on the
        same free stock in sequence, so two lines of 6 against 10 in stock
        see 6 and 4, not 6 and 6.
        """
        coverage = {}
        by_warehouse = defaultdict(lambda: self.browse())
        for line in self:
            by_warehouse[line.order_id.warehouse_id] |= line
        for warehouse, lines in by_warehouse.items():
            products = lines.product_id.with_context(warehouse_id=warehouse.id or False)
            free = {product.id: max(product.free_qty, 0.0) for product in products}
            remaining = defaultdict(dict)
            for line in lines.sorted(lambda l: (l.order_id.id, l.sequence, l.id)):
                pool = remaining[line.order_id.id]
                available = pool.setdefault(line.product_id.id, free[line.product_id.id])
                covered = min(available, line._cost_source_qty())
                pool[line.product_id.id] = available - covered
                coverage[line.id] = covered
        return coverage

    def _cost_source_currency(self):
        self.ensure_one()
        return self.currency_id or self.company_id.currency_id

    def _cost_source_delivery_date(self):
        self.ensure_one()
        moment = self.order_id.commitment_date or self.order_id.expected_date
        if not moment:
            return None
        return fields.Datetime.context_timestamp(self, moment).date()

    def _cost_source_resolve(self, date, qty_from_stock):
        """The engine's resolution for this line, as of ``date``."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return self.product_id.with_company(company)._resolve_cost(
            qty=self._cost_source_qty(),
            date=date,
            currency=self._cost_source_currency(),
            company=company,
            qty_from_stock=qty_from_stock,
            delivery_date=self._cost_source_delivery_date(),
        )
