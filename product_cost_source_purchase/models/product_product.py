# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from datetime import datetime, time, timedelta

from odoo import fields, models
from odoo.tools.float_utils import float_compare
from odoo.tools.misc import format_date

from odoo.addons.product_cost_source.tools.cost_source import CostSource

#: Purchase order states that make a line a confirmed repricing event.
CONFIRMED_STATES = ("purchase",)
#: States of an open request for quotation (quoted, not confirmed).
RFQ_STATES = ("draft", "sent")
#: How many days back a pre-filled RFQ price may have taken its exchange rate.
RATE_LAG_DAYS = 7


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
            source = self._cost_source_from_purchase_line(
                rfq, qty, currency, company, key="rfq"
            )
            # A price Odoo filled in from the vendor's price list is our own
            # number echoed back, not the vendor's answer: the request is
            # reported, the confidence comes from the other evidence.
            if not self._cost_source_rfq_answered(rfq):
                source.indicative = False
                source.pending = True
            candidates.append(source)
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
        """The latest line of an open request for quotation, if any.

        Only RFQs dated within the price age window count: a stale draft
        RFQ left open for years is not a quote anyone would honour.
        """
        until = datetime.combine(date, time.max)
        since = datetime.combine(self._cost_source_cutoff(date), time.min)
        # No price filter here: an RFQ line at zero is a request still waiting
        # for its answer, which is worth reporting too.
        domain = [
            term
            for term in self._cost_source_purchase_domain(company)
            if term != ("price_unit", ">", 0)
        ]
        return (
            self.env["purchase.order.line"]
            .sudo()
            .search(
                domain
                + [
                    ("order_id.state", "in", RFQ_STATES),
                    ("order_id.date_order", ">=", since),
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
            basis=key,
            source_price=price,
            source_currency=line.currency_id,
            indicative=key == "rfq",
            reference=line.order_id.name,
        )

    def _cost_source_rfq_answered(self, line):
        """Whether the RFQ line's price was typed in, i.e. is the vendor's answer.

        Odoo pre-fills an RFQ line with the vendor's price list price (or the
        product cost when the vendor has none), converted to the RFQ's
        currency and unit. A line still at that figure carries no answer.

        The conversion is checked with the rates of the order date, of the day
        the line was created, and of the week before each: Odoo converts with
        the latest rate it has when the line is filled in, and the day's own
        rate is often loaded later. The discount must match too. A price of
        zero is never an answer.
        """
        self.ensure_one()
        currency = line.currency_id or line.company_id.currency_id
        if currency.is_zero(line.price_unit):
            return False
        order = line.order_id
        company = line.company_id or self.env.company
        uom = line.product_uom_id or self.uom_id
        moments = [order.date_order, line.create_date]
        days = {
            fields.Datetime.context_timestamp(self, moment).date() - timedelta(days=back)
            for moment in moments
            if moment
            for back in range(RATE_LAG_DAYS + 1)
        }
        vendor = order.partner_id.commercial_partner_id
        sellers = (
            self.with_context(active_test=False)
            .sudo()
            .seller_ids.filtered(
                lambda s: s.partner_id.commercial_partner_id == vendor
                and (not s.product_id or s.product_id == self)
            )
        )
        prefills = []
        for day in days:
            for seller in sellers:
                price = self._cost_source_convert(
                    seller.price, seller.currency_id, currency, company, day
                )
                prefills.append(
                    (
                        seller.product_uom_id._compute_price(price, uom)
                        if seller.product_uom_id
                        else price,
                        seller.discount or 0.0,
                    )
                )
            if not sellers:
                cost = self._cost_source_convert(
                    self.standard_price, self.cost_currency_id, currency, company, day
                )
                prefills.append((self.uom_id._compute_price(cost, uom), 0.0))
        return not any(
            currency.compare_amounts(price, line.price_unit) == 0
            and float_compare(discount, line.discount or 0.0, precision_digits=2) == 0
            for price, discount in prefills
        )

    # -- wording -----------------------------------------------------------

    def _cost_source_basis_text(self, source):
        if source.basis == "purchase":
            return self.env._(
                "purchased on %(date)s (%(name)s)",
                date=format_date(self.env, source.priced_on),
                name=source.reference,
            )
        return super()._cost_source_basis_text(source)

    def _cost_source_describe(self, source, date, currency):
        if source.key == "rfq" and source.pending:
            return self.env._(
                "Price requested on %(name)s (%(date)s), no answer yet.",
                name=source.reference,
                date=format_date(self.env, source.priced_on),
            )
        if source.key == "rfq":
            return self.env._(
                "Indicative. Quoted %(price)s on %(name)s, not yet confirmed.",
                price=self._cost_source_price_text(source, currency),
                name=source.reference,
            )
        return super()._cost_source_describe(source, date, currency)
