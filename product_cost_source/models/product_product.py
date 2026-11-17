# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare, float_is_zero
from odoo.tools.misc import NON_BREAKING_SPACE, format_amount, format_date, formatLang

from ..tools.cost_source import CONFIDENCE_ORDER, CostResolution, CostSource


class ProductProduct(models.Model):
    _inherit = "product.product"

    # -- extension point ---------------------------------------------------

    def _cost_sources(self, qty, date, currency, company, qty_from_stock=0.0):
        """Return the cost sources covering ``qty``, best-first.

        This is the extension point. A module that knows another way to
        establish a cost overrides this, calls super(), and appends its own
        sources; resolution, confidence and evidence then apply to them
        unchanged.

        ``qty_from_stock`` is supplied by the caller rather than discovered
        here. This module does not know what a demand is -- a sale line, a
        manufacturing order and a forecast each reason about availability
        differently, and each is entitled to its own answer.
        """
        self.ensure_one()
        rounding = self.uom_id.rounding
        sources = []

        covered = max(0.0, min(qty_from_stock, qty))
        if not float_is_zero(covered, precision_rounding=rounding):
            unvalued = company.currency_id.is_zero(self.standard_price)
            sources.append(
                CostSource(
                    key="stock",
                    qty=covered,
                    unit_price=self._cost_source_convert(
                        self.standard_price, company.currency_id, currency, company, date
                    ),
                    source_price=self.standard_price,
                    source_currency=company.currency_id,
                    # Stock was bought at a price we actually paid, so its age
                    # is not in question: we own the goods at that cost --
                    # unless it carries no value at all, which proves nothing.
                    priced_on=date,
                    in_force=not unvalued,
                    unvalued=unvalued,
                    likely=(
                        self._cost_source_vendor(covered, date, currency, company)
                        if unvalued
                        else None
                    ),
                )
            )

        remaining = qty - covered
        if float_compare(remaining, 0.0, precision_rounding=rounding) > 0:
            vendor = self._cost_source_vendor(remaining, date, currency, company)
            if vendor:
                sources.append(vendor)
        return sources

    # -- built-in sources --------------------------------------------------

    def _cost_source_vendor(self, qty, date, currency, company):
        """The best available evidence of what a vendor would charge for ``qty``.

        Candidates come from :meth:`_cost_source_price_candidates`, which is the
        second extension point: modules contribute other ways of knowing a
        price, and the best-evidenced one wins. They compete rather than
        accumulate, because they are all answering the same question.

        A newer indicative candidate that lost to firm evidence is not thrown
        away: it is attached to the winner as a note, because "the vendor
        quoted something else last week" is worth knowing.
        """
        self.ensure_one()
        everything = self._cost_source_price_candidates(qty, date, currency, company)
        # A pending candidate (a price asked for, not given) is not a price:
        # it never competes, it is only reported beside the winner.
        pending = [source for source in everything if source.pending]
        candidates = [source for source in everything if not source.pending]
        if not candidates:
            return None
        cutoff = self._cost_source_cutoff(date)
        ranked = sorted(candidates, key=lambda s: self._cost_source_rank(s, cutoff))
        best = ranked[0]
        if not best.indicative:
            best.notes = [
                other
                for other in ranked[1:]
                if other.indicative
                and other.priced_on
                and (best.priced_on is None or other.priced_on > best.priced_on)
            ]
        best.notes = best.notes + pending
        return best

    def _cost_source_cutoff(self, date):
        """Oldest date a price may be established on and still count as current."""
        months = self.env["res.config.settings"]._price_age_months()
        return date - relativedelta(months=months)

    def _cost_source_rank(self, source, cutoff=None):
        """Ordering over price evidence, best first.

        An agreement in force outranks loose evidence, because it is a promise
        rather than an observation. Then a confirmed price established within
        the age window; then an indicative one (quoted, not confirmed); then
        everything older. Within a tier the most recently established price
        wins, whoever contributed it -- a plugin cannot jump the queue merely
        by being a plugin. Undated evidence sorts last: it may well be current,
        but nothing on file says so.
        """
        if source.in_force:
            tier = 0
        elif source.indicative:
            tier = 2
        elif cutoff and source.priced_on and source.priced_on >= cutoff:
            tier = 1
        else:
            tier = 3
        return (
            tier,
            0 if source.priced_on else 1,
            -source.priced_on.toordinal() if source.priced_on else 0,
        )

    def _cost_source_price_candidates(self, qty, date, currency, company):
        """Return every known indication of a vendor price for ``qty``.

        Extension point. Override, call super(), and append your own evidence;
        ranking, confidence and evidence-reporting then apply to it unchanged.
        """
        self.ensure_one()
        # _select_seller and the seller filters read self.env.company, so the
        # lookup must run in the company the cost is being resolved for.
        self = self.with_company(company)
        candidates = []
        seller = self._select_seller(quantity=qty, date=date, uom_id=self.uom_id)
        if seller:
            candidates.append(self._cost_source_from_seller(seller, qty, currency, company, date))
        fallback = self._cost_source_last_known_seller(qty)
        if fallback and fallback != seller:
            candidates.append(self._cost_source_from_seller(fallback, qty, currency, company, date))
        return candidates

    @api.model
    def _cost_source_seller_in_force(self, seller, date):
        """Whether a supplier price is a promise that still holds on ``date``.

        Only an END date makes a promise. A price with a start date and no end
        is when the vendor last set the price, not an undertaking to keep it:
        it is a dated last-known price, judged by its age like any other.
        """
        return bool(
            seller.date_end
            and seller.date_end >= date
            and (not seller.date_start or seller.date_start <= date)
        )

    def _cost_source_last_known_seller(self, qty):
        """The most recent supplier price on file, whether or not it still applies.

        Used when Odoo's own seller lookup finds nothing, which happens when
        every agreement has lapsed. The price is still the last thing we knew;
        it is reported as evidence rather than as a commitment.
        """
        self.ensure_one()
        # Same company / variant / active-partner filter Odoo's own seller
        # selection applies, so a price meant for another company or another
        # variant is never offered as "the last known price". ``params`` is
        # passed explicitly because the purchase module's override of
        # ``_get_filtered_supplier`` makes it a required argument.
        candidates = self.seller_ids._get_filtered_supplier(
            self.env.company, self, params=False
        ).filtered(lambda s: not s.min_qty or s.min_qty <= qty)
        if not candidates:
            return self.env["product.supplierinfo"]
        dated = candidates.filtered("date_start")
        if dated:
            return max(dated, key=lambda s: s.date_start)
        return candidates.sorted("sequence")[0]

    def _cost_source_from_seller(self, seller, qty, currency, company, date, in_force=None):
        if in_force is None:
            in_force = self._cost_source_seller_in_force(seller, date)
        priced_on, basis = self._cost_source_seller_date(seller, date)
        # The discounted price, already per unit of the product: what we
        # would pay.
        price = seller.price_discounted
        return CostSource(
            key="vendor",
            qty=qty,
            unit_price=self._cost_source_convert(
                price, seller.currency_id, currency, company, date
            ),
            priced_on=priced_on,
            basis=basis or "",
            source_price=price,
            source_currency=seller.currency_id,
            in_force_until=seller.date_end or None,
            in_force=in_force,
        )

    # -- freshness of a supplier price --------------------------------------

    #: Supplier price fields whose tracked change means the price was reset.
    _cost_source_seller_price_fields = ("price", "discount")

    def _cost_source_seller_date(self, seller, date):
        """``(date, basis)``: when this supplier price was last established.

        The most recent of the dated evidence that :meth:`_cost_source_seller_dates`
        offers, ignoring anything after ``date``. ``(None, None)`` when there
        is none -- unknown is never fresh.
        """
        dated = [
            (on, basis)
            for on, basis in self._cost_source_seller_dates(seller)
            if on and on <= date
        ]
        if not dated:
            return None, None
        return max(dated, key=lambda item: item[0])

    def _cost_source_seller_dates(self, seller):
        """Every dated piece of evidence that this supplier price was (re)set.

        Extension point: a module that knows another way a price gets
        confirmed (a dated note, a vendor portal...) overrides this, calls
        super() and appends ``(date, basis)`` pairs, then words its ``basis``
        in :meth:`_cost_source_basis_text`.

        Built in:

        * ``start``: the start date of the price, when it has one;
        * ``changed``: the last change of its price or discount in the record's
          tracked history (when the supplier price is tracked in the chatter);
        * ``entered``: the day the line was created -- with no change since,
          that is when its price was set (any tracked change is later, so it
          wins when there is one).

        ``write_date`` is never used: any edit, or a bulk import, touches it,
        and it says nothing about the price.
        """
        dates = []
        if seller.date_start:
            dates.append((seller.date_start, "start"))
        changed = self._cost_source_seller_tracked_change(seller)
        if changed:
            dates.append((changed, "changed"))
        if seller.create_date:
            dates.append((self._cost_source_local_date(seller.create_date), "entered"))
        return dates

    def _cost_source_local_date(self, moment):
        return fields.Datetime.context_timestamp(self, moment).date()

    def _cost_source_seller_tracked_change(self, seller):
        """Date of the last tracked change of the seller's price or discount.

        Read straight from the tracking tables, so it works whichever module
        puts supplier prices in the chatter, and costs one query.
        """
        if not seller.id or "mail.tracking.value" not in self.env:
            return None
        field_ids = [
            field.id
            for name in self._cost_source_seller_price_fields
            for field in [self.env["ir.model.fields"]._get("product.supplierinfo", name)]
            if field
        ]
        if not field_ids:
            return None
        self.env.cr.execute(
            """
            SELECT max(message.date)
              FROM mail_tracking_value tracking
              JOIN mail_message message ON message.id = tracking.mail_message_id
             WHERE message.model = 'product.supplierinfo'
               AND message.res_id = %s
               AND tracking.field_id = ANY(%s)
            """,
            [seller.id, field_ids],
        )
        moment = self.env.cr.fetchone()[0]
        return self._cost_source_local_date(moment) if moment else None

    def _cost_source_convert(self, amount, from_currency, to_currency, company, date):
        if not from_currency or not to_currency or from_currency == to_currency:
            return amount
        return from_currency._convert(
            from_amount=amount,
            to_currency=to_currency,
            company=company,
            date=date,
            round=False,
        )

    # -- resolution --------------------------------------------------------

    def _resolve_cost(
        self,
        qty=1.0,
        date=None,
        currency=None,
        company=None,
        qty_from_stock=0.0,
        delivery_date=None,
    ):
        """Resolve a unit cost for ``qty`` and report the evidence behind it."""
        self.ensure_one()
        company = company or self.env.company
        currency = currency or company.currency_id
        date = date or fields.Date.context_today(self)

        sources = self._cost_sources(qty, date, currency, company, qty_from_stock)
        resolution = CostResolution(sources=sources)
        if not sources:
            resolution.evidence.append(
                self.env._("Unknown. No vendor price and no purchase history.")
            )
            return resolution

        covered = sum(source.qty for source in sources)
        resolution.unit_cost = (
            sum(source.subtotal for source in sources) / covered if covered else 0.0
        )
        resolution.confidence = self._cost_source_confidence(sources, date, qty)
        resolution.evidence = self._cost_source_evidence(sources, date, qty, currency)
        resolution.warnings = self._cost_source_warnings(
            sources, delivery_date, date, currency
        )
        resolution.notes = [
            self._cost_source_describe(note, date, currency)
            for source in sources
            for note in source.notes
        ]
        return resolution

    def _cost_source_level(self, source, cutoff):
        """The confidence one source deserves on its own."""
        if source.unvalued:
            return "unknown"
        if source.in_force:
            return "firm"
        if source.indicative:
            return "indicative"
        if source.priced_on is None or source.priced_on < cutoff:
            return "estimated"
        return "firm"

    def _cost_source_uncovered(self, sources, qty):
        """How much of ``qty`` no source prices (never negative)."""
        if qty is None:
            return 0.0
        remaining = qty - sum(source.qty for source in sources)
        if float_compare(remaining, 0.0, precision_rounding=self.uom_id.rounding) > 0:
            return remaining
        return 0.0

    def _cost_source_confidence(self, sources, date, qty=None):
        """The weakest level among the contributing sources.

        A blend is no better than its weakest half: quoting a firm price for
        part of a line and a guess for the rest is still quoting a guess. A
        part nobody can price at all makes the whole Unknown.
        """
        if not sources or self._cost_source_uncovered(sources, qty):
            return "unknown"
        cutoff = self._cost_source_cutoff(date)
        return min(
            (self._cost_source_level(source, cutoff) for source in sources),
            key=CONFIDENCE_ORDER.index,
        )

    def _cost_source_evidence(self, sources, date, qty, currency=None):
        currency = currency or self.env.company.currency_id
        blended = len(sources) > 1
        uncovered = self._cost_source_uncovered(sources, qty)
        evidence = []
        for source in sources:
            if source.key == "stock":
                evidence.append(
                    self._cost_source_describe_stock(source, qty, currency, blended)
                )
                # Cite the likely cost unless the same evidence already
                # prices the balance and is described below.
                if source.likely and not blended:
                    # A vendor price of zero is obviously wrong data, not a
                    # likely cost: say so instead of citing it as a figure.
                    if currency.is_zero(source.likely.unit_price):
                        evidence.append(
                            self.env._(
                                "Vendor price at %(price)s, from: %(evidence)s",
                                price=format_amount(self.env, 0.0, currency),
                                evidence=self._cost_source_describe(
                                    source.likely, date, currency
                                ),
                            )
                        )
                        continue
                    evidence.append(
                        self.env._(
                            "Likely cost %(price)s, from: %(evidence)s",
                            price=self._cost_source_price_text(
                                source.likely, currency
                            ),
                            evidence=self._cost_source_describe(
                                source.likely, date, currency
                            ),
                        )
                    )
                continue
            sentence = self._cost_source_describe(source, date, currency)
            if blended:
                sentence += self.env._(
                    " Covers %(qty)s of %(total)s.",
                    qty=self._cost_source_format_qty(source.qty),
                    total=self._cost_source_format_qty(qty),
                )
            evidence.append(sentence)
        if uncovered:
            evidence.append(
                self.env._(
                    "Unknown. No vendor price for the other %(qty)s.",
                    qty=self._cost_source_format_qty(uncovered),
                )
            )
        return evidence

    def _cost_source_describe_stock(self, source, qty, currency, blended):
        price = self._cost_source_price_text(source, currency)
        if source.unvalued:
            if float_compare(source.qty, qty, precision_rounding=self.uom_id.rounding) >= 0:
                return self.env._("Unknown. Covered from stock with no cost value.")
            return self.env._(
                "Unknown. %(qty)s of %(total)s covered from stock with no cost value.",
                qty=self._cost_source_format_qty(source.qty),
                total=self._cost_source_format_qty(qty),
            )
        if float_compare(source.qty, qty, precision_rounding=self.uom_id.rounding) >= 0:
            return self.env._("Firm. Covered from stock at %(price)s.", price=price)
        if blended:
            return self.env._(
                "Firm. %(qty)s of %(total)s covered from stock at %(price)s; "
                "balance at vendor price.",
                qty=self._cost_source_format_qty(source.qty),
                total=self._cost_source_format_qty(qty),
                price=price,
            )
        return self.env._(
            "Firm. %(qty)s of %(total)s covered from stock at %(price)s; "
            "no known price for the balance.",
            qty=self._cost_source_format_qty(source.qty),
            total=self._cost_source_format_qty(qty),
            price=price,
        )

    def _cost_source_describe(self, source, date, currency):
        """One sentence, verdict first, describing a piece of price evidence.

        Extension point: a module contributing its own kind of evidence
        (``source.key``) overrides this to word it, and calls super() for the
        rest. The basis of a dated price is worded separately, in
        :meth:`_cost_source_basis_text`.
        """
        months = self.env["res.config.settings"]._price_age_months()
        price = self._cost_source_price_text(source, currency)
        if source.in_force and source.in_force_until:
            return self.env._(
                "Firm. %(price)s, vendor price list valid to %(until)s.",
                price=price,
                until=format_date(self.env, source.in_force_until),
            )
        if source.in_force:
            return self.env._("Firm. %(price)s, vendor agreement in force.", price=price)
        if source.indicative:
            return self.env._(
                "Indicative. Quoted %(price)s, not yet confirmed.", price=price
            )
        if source.priced_on is None:
            return self.env._(
                "Estimated. %(price)s, the vendor price on file is undated, so "
                "its age cannot be established.",
                price=price,
            )
        basis = self._cost_source_basis_text(source)
        if source.priced_on < self._cost_source_cutoff(date):
            return self.env._(
                "Estimated. %(price)s, %(basis)s, over %(months)s months ago. "
                "No contract in force.",
                price=price,
                basis=basis,
                months=months,
            )
        return self.env._("Firm. %(price)s, %(basis)s.", price=price, basis=basis)

    def _cost_source_basis_text(self, source):
        """What established ``source.priced_on``, as a clause ("vendor price
        changed on {date}").

        Extension point: a module adding a ``basis`` (see
        :meth:`_cost_source_seller_dates`) words it here and calls super().
        """
        on = format_date(self.env, source.priced_on)
        if source.basis == "changed":
            return self.env._("vendor price changed on %(date)s", date=on)
        if source.basis == "entered":
            return self.env._("vendor price entered on %(date)s", date=on)
        if source.basis == "start":
            return self.env._("vendor price valid from %(date)s", date=on)
        return self.env._("last known price %(date)s", date=on)

    def _cost_source_price_text(self, source, currency):
        """The price as the evidence states it, then in ``currency``.

        In one currency, the usual amount ("$ 75.00"). When the evidence is in
        another currency, its own figure comes first and the conversion
        follows in brackets, both with their ISO code so two dollars never
        read alike: "160.00 CAD (≈ 114.11 USD)".
        """
        other = source.source_currency
        if other and currency and other != currency and source.source_price is not None:
            return self.env._(
                "%(price)s (≈ %(converted)s)",
                price=self._cost_source_format_code(source.source_price, other),
                converted=self._cost_source_format_code(source.unit_price, currency),
            )
        return format_amount(self.env, source.unit_price, currency)

    def _cost_source_format_code(self, amount, currency):
        """``amount`` with the currency's ISO code: "160.00 CAD"."""
        return "%s%s%s" % (
            formatLang(self.env, amount, digits=currency.decimal_places),
            NON_BREAKING_SPACE,
            currency.name,
        )

    def _cost_source_warnings(self, sources, delivery_date, date=None, currency=None):
        """Flag what makes a cost untrustworthy despite the evidence.

        Stock carried at no value is flagged whatever the dates: its cost is a
        blank, not a price.

        Then a price that is firm today but will not be by delivery.

        The case a plain age check cannot see: nothing is stale, and the quote
        is still wrong. Only a price still in force on ``date`` can warn: an
        expired price is already reported as not in force, and warning that it
        "expires" on a past date would be noise.
        """
        date = date or fields.Date.context_today(self)
        warnings = []
        for source in sources:
            if source.unvalued:
                warnings.append(
                    self.env._(
                        "Warning. Stock has no cost value: the cost of %(price)s "
                        "is not reliable.",
                        price=format_amount(
                            self.env,
                            source.unit_price,
                            currency or self.env.company.currency_id,
                        ),
                    )
                )
        if not delivery_date:
            return warnings
        for source in sources:
            if (
                source.in_force
                and source.in_force_until
                and date <= source.in_force_until < delivery_date
            ):
                warnings.append(
                    self.env._(
                        "Warning. Vendor price expires %(expiry)s, before this "
                        "line's delivery date of %(delivery)s.",
                        expiry=format_date(self.env, source.in_force_until),
                        delivery=format_date(self.env, delivery_date),
                    )
                )
        return warnings

    def _cost_source_format_qty(self, qty):
        return ("%.2f" % qty).rstrip("0").rstrip(".")
