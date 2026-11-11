# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import itertools

from odoo import api, fields, models

from .zeffy_record_mixin import cents, from_timestamp


class ZeffyPayment(models.Model):
    _name = "zeffy.payment"
    _inherit = ["zeffy.record.mixin"]
    _description = "Zeffy Payment"
    _order = "payment_date desc, id desc"

    _unique_zeffy_id = models.Constraint(
        "unique(company_id, zeffy_id)",
        "This Zeffy payment is already synchronized for this company.",
    )

    payment_date = fields.Datetime(string="Date", readonly=True, index=True)
    description = fields.Char(readonly=True, help="Campaign title as recorded on the payment.")
    currency_id = fields.Many2one("res.currency", readonly=True)
    amount = fields.Monetary(readonly=True)
    eligible_amount = fields.Monetary(
        string="Receipt-eligible amount",
        readonly=True,
        help="Part of the amount eligible for a tax receipt.",
    )
    refunded_amount = fields.Monetary(readonly=True)
    status = fields.Char(readonly=True)
    payment_type = fields.Selection(
        [("online", "Online"), ("manual", "Manual"), ("imported", "Imported")],
        string="Source",
        readonly=True,
    )
    payment_method = fields.Char(readonly=True)
    refund_status = fields.Selection(
        [("none", "Not refunded"), ("partial", "Partially refunded"), ("full", "Refunded")],
        readonly=True,
    )
    campaign_category = fields.Char(readonly=True)
    campaign_id = fields.Many2one("zeffy.campaign", readonly=True, index=True)
    utm_campaign_id = fields.Many2one(
        related="campaign_id.utm_campaign_id", string="UTM Campaign", store=True
    )
    contact_id = fields.Many2one("zeffy.contact", string="Zeffy contact", readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Donor", index=True, ondelete="set null")
    buyer_email = fields.Char(readonly=True, help="Email entered by the buyer on the Zeffy form.")
    fund_code = fields.Char(readonly=True)
    fund_name = fields.Char(string="Fund", readonly=True)
    tribute_type = fields.Char(readonly=True)
    tribute_name = fields.Char(string="Tribute to", readonly=True)
    receipt_url = fields.Char(string="Tax receipt", readonly=True)
    is_recurring = fields.Boolean(string="Monthly giving", readonly=True)
    recurring_interval = fields.Char(string="Recurrence", readonly=True)
    recurring_status = fields.Char(string="Recurrence status", readonly=True)
    subscription_id = fields.Char(string="Zeffy subscription", readonly=True, index=True)
    recurring_period_end = fields.Datetime(string="Current period ends", readonly=True)
    zeffy_deleted = fields.Boolean(
        string="Deleted in Zeffy",
        readonly=True,
        help="Zeffy no longer returns this payment.",
    )

    @api.depends("payment_date", "partner_id", "amount", "currency_id")
    def _compute_display_name(self):
        for payment in self:
            parts = [
                fields.Date.to_string(payment.payment_date) if payment.payment_date else "",
                payment.partner_id.display_name or "",
                f"{payment.amount:.2f} {payment.currency_id.name or ''}".strip(),
            ]
            payment.display_name = " - ".join(p for p in parts if p)

    @api.model
    def _zeffy_prepare_values(self, data, company, record, cache):
        Contact = self.env["zeffy.contact"]
        buyer = data.get("buyer") or {}
        contact = Contact.browse()
        if data.get("contact"):
            contact = Contact._zeffy_from_buyer(data["contact"], buyer, company, cache)
        if contact:
            partner = contact.partner_id
        elif record.partner_id:
            partner = record.partner_id
        else:
            partner = Contact._zeffy_match_partner(
                company,
                email=buyer.get("email"),
                first_name=buyer.get("first_name"),
                last_name=buyer.get("last_name"),
                address=buyer.get("address"),
                company_name=buyer.get("company_name") if buyer.get("is_corporate") else None,
            )
        campaign = self.env["zeffy.campaign"]._zeffy_get_or_stub(
            data.get("campaign_id"), data.get("description"), company, cache
        )
        fund = data.get("fund") or {}
        tribute = next(
            (item["tribute"] for item in data.get("items") or [] if item.get("tribute")), {}
        )
        recurring = data.get("recurring") or {}
        refunded = sum(
            refund.get("amount") or 0
            for refund in data.get("refunds") or []
            if refund.get("status") == "succeeded"
        )
        return {
            "payment_date": from_timestamp(data.get("created")),
            "description": data.get("description"),
            "currency_id": self._zeffy_currency(data.get("currency"), company, cache).id,
            "amount": cents(data.get("amount")),
            "eligible_amount": cents(data.get("eligible_amount")),
            "refunded_amount": cents(refunded),
            "status": data.get("status"),
            "payment_type": self._zeffy_selection("payment_type", data.get("type")),
            "payment_method": (data.get("payment_method") or {}).get("type"),
            "refund_status": self._zeffy_selection("refund_status", data.get("refund_status")),
            "campaign_category": data.get("campaign_category"),
            "campaign_id": campaign.id,
            "contact_id": contact.id,
            "partner_id": partner.id,
            "buyer_email": buyer.get("email"),
            "fund_code": fund.get("code"),
            "fund_name": self._zeffy_fund_name(fund.get("name")),
            "tribute_type": tribute.get("type"),
            "tribute_name": tribute.get("honouree_name"),
            "receipt_url": data.get("receipt_url"),
            "is_recurring": bool(recurring.get("is_recurring")),
            "recurring_interval": recurring.get("interval"),
            "recurring_status": recurring.get("status"),
            "subscription_id": recurring.get("subscription_id"),
            "recurring_period_end": from_timestamp(recurring.get("current_period_end")),
        }

    @api.model
    def _zeffy_fund_name(self, names):
        """Fund names come keyed by locale (EN, FR, ES)."""
        if not names:
            return False
        if isinstance(names, str):
            return names
        lang = (self.env.lang or "en_US")[:2].upper()
        return names.get(lang) or next((name for name in names.values() if name), False)

    @api.model
    def _zeffy_sync(self, client, company, cache):
        existing = cache[self._name]
        seen = set()
        touched = self.browse()
        # Zeffy's default listing omits failed payments; they are only listed
        # on request, and a pending payment that fails would otherwise look
        # deleted.
        listings = (client.iter_list("payments"), client.iter_list("payments", {"status": "failed"}))
        for data in itertools.chain(*listings):
            if data["id"] in seen:
                continue
            seen.add(data["id"])
            record, is_changed = self._zeffy_upsert(data, company, cache)
            if is_changed:
                touched |= record
        # The pass is complete: flag what Zeffy no longer returns.
        for zeffy_id, record in existing.items():
            deleted = zeffy_id not in seen
            if record.zeffy_deleted != deleted:
                record.zeffy_deleted = deleted
                touched |= record
        if touched:
            touched._zeffy_payment_synced()
        return len(touched)

    def _zeffy_payment_synced(self):
        """Hook: ``self`` holds every payment created or updated by a
        synchronization, including those flagged or unflagged as deleted in
        Zeffy. Override to propagate them, e.g. to a donation model."""
        return True
