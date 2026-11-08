# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from datetime import datetime, time

from odoo import fields, models
from odoo.tools.misc import format_amount, format_date

from odoo.addons.product_cost_source.tools.cost_source import CostSource

#: Purchase order states that make a line a confirmed repricing event.
CONFIRMED_STATES = ("purchase",)
#: States of an open request for quotation (quoted, not confirmed).
RFQ_STATES = ("draft", "sent")


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _cost_source_price_candidates(self, qty, date, currency, company):
        candidates = super()._cost_source_price_candidates(qty, date, currency, company)
        purchase = self._cost_source_last_purchase_line(date, company)
        if purchase:
            candidates.append(
                self._cost_source_from_purchase_line(
                    purchase, qty, currency, company, key="purchase"
                )
            )
        rfq = self._cost_source_open_rfq_line(date, company)
        if rfq:
            candidates.append(
                self._cost_source_from_purchase_line(
                    rfq, qty, currency, company, key="rfq"
                )
            )
        return candidates

    # -- lookups -----------------------------------------------------------

    def _cost_source_purchase_domain(self, company):
        self.ensure_one()
        return [
            ("product_id", "=", self.id),
            ("company_id", "=", company.id),
            ("display_type", "=", False),
            ("price_unit", ">", 0),
        ]

    def _cost_source_last_purchase_line(self, date, company):
        """The latest confirmed purchase order line up to ``date``.

        Read as superuser, but scoped to this variant and company: a
        salesperson needs the evidence without needing Purchase access, and
        only the date, price and order number are used.
        """
        until = datetime.combine(date, time.max)
        return (
            self.env["purchase.order.line"]
            .sudo()
            .search(
                self._cost_source_purchase_domain(company)
                + [
                    ("order_id.state", "in", CONFIRMED_STATES),
                    ("order_id.date_approve", "<=", until),
                ],
                order="date_approve desc, id desc",
                limit=1,
            )
        )

    def _cost_source_open_rfq_line(self, date, company):
        """The latest line of an open request for quotation, if any."""
        until = datetime.combine(date, time.max)
        return (
            self.env["purchase.order.line"]
            .sudo()
            .search(
                self._cost_source_purchase_domain(company)
                + [
                    ("order_id.state", "in", RFQ_STATES),
                    ("order_id.date_order", "<=", until),
                ],
                order="date_order desc, id desc",
                limit=1,
            )
        )

    def _cost_source_from_purchase_line(self, line, qty, currency, company, key):
        moment = line.order_id.date_approve if key == "purchase" else line.order_id.date_order
        priced_on = fields.Datetime.context_timestamp(self, moment).date()
        price = line.product_uom_id._compute_price(line.price_unit_discounted, self.uom_id)
        return CostSource(
            key=key,
            qty=qty,
            unit_price=self._cost_source_convert(
                price, line.currency_id, currency, company, priced_on
            ),
            priced_on=priced_on,
            indicative=key == "rfq",
            reference=line.order_id.name,
        )

    # -- wording -----------------------------------------------------------

    def _cost_source_describe(self, source, date, currency):
        if source.key == "purchase":
            if source.priced_on < self._cost_source_cutoff(date):
                return self.env._(
                    "Estimated. Last purchased %(date)s, over %(months)s months "
                    "ago. No contract in force.",
                    date=format_date(self.env, source.priced_on),
                    months=self.env["res.config.settings"]._price_age_months(),
                )
            return self.env._(
                "Firm. Last purchased %(date)s.",
                date=format_date(self.env, source.priced_on),
            )
        if source.key == "rfq":
            return self.env._(
                "Indicative. Quoted %(price)s on RFQ %(name)s, not yet confirmed.",
                price=format_amount(self.env, source.unit_price, currency),
                name=source.reference,
            )
        return super()._cost_source_describe(source, date, currency)
