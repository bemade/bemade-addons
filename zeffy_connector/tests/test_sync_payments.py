# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Use case: Zeffy payments (donations) are synchronized into Odoo.

Acceptance criteria
- Each Zeffy payment becomes one ``zeffy.payment`` with amounts in currency
  units (Zeffy sends cents), its UTC date, status, source type, payment
  method, refund status and refunded amount, fund, tribute, tax receipt link,
  campaign, buyer email, Zeffy contact and Odoo contact.
- Monthly-giving payments carry their recurrence (interval, status,
  subscription id, current period end).
- A payment whose Zeffy contact was not synchronized yet gets one built from
  the buyer details; a payment without contact is matched from its buyer.
- Re-running is idempotent on the Zeffy id; a changed payment (refund,
  receipt issued later) is updated in place; an unchanged one is not written.
- ``_zeffy_payment_synced()`` receives exactly the payments created or
  updated by the run.
- Failed payments, which Zeffy lists only on request, are synchronized too:
  a pending payment that fails is updated, not taken for a deleted one.
- After a complete pass, a payment Zeffy no longer returns is flagged deleted
  in Zeffy; it is unflagged if it comes back. A failed pass flags nothing.
- Records of one company are never matched against another company's.
"""

import datetime
from unittest.mock import patch

from odoo.tests import tagged

from ..models.zeffy_client import ZeffyError
from .common import (
    FakeResponse,
    ZeffyCase,
    make_campaign,
    make_contact,
    make_payment,
)


@tagged("post_install", "-at_install")
class TestZeffySyncPayments(ZeffyCase):
    def setUp(self):
        super().setUp()
        self.campaign_data = make_campaign(title="Annual Campaign")
        self.contact_data = make_contact()
        self.api.campaigns = [self.campaign_data]
        self.api.contacts = [self.contact_data]

    def _payment(self, data):
        return self.Payment.with_context(active_test=False).search(
            [("zeffy_id", "=", data["id"])]
        )

    def _add(self, **over):
        data = make_payment(self.contact_data, self.campaign_data, **over)
        self.api.payments.append(data)
        return data

    def test_payment_values(self):
        data = self._add(
            amount=12550,
            eligible_amount=10000,
            fund={"id": "f1", "object": "fund", "code": "4100", "name": {"FR": "Soins", "EN": "Care"}},
        )
        data["items"][0]["tribute"] = {"type": "in_memory_of", "honouree_name": "Jo Doe"}
        self.sync()
        payment = self._payment(data)
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment.amount, 125.50)
        self.assertEqual(payment.eligible_amount, 100.0)
        self.assertEqual(payment.currency_id, self.cad)
        self.assertEqual(payment.payment_date, datetime.datetime(2026, 1, 1, 13, 0))
        self.assertEqual(payment.status, "succeeded")
        self.assertEqual(payment.payment_type, "online")
        self.assertEqual(payment.payment_method, "card")
        self.assertEqual(payment.refund_status, "none")
        self.assertEqual(payment.fund_code, "4100")
        self.assertIn(payment.fund_name, ("Soins", "Care"))
        self.assertEqual(payment.tribute_type, "in_memory_of")
        self.assertEqual(payment.tribute_name, "Jo Doe")
        self.assertEqual(payment.receipt_url, data["receipt_url"])
        self.assertEqual(payment.campaign_id.zeffy_id, self.campaign_data["id"])
        self.assertEqual(payment.utm_campaign_id.name, "Annual Campaign")
        self.assertEqual(payment.contact_id.zeffy_id, self.contact_data["id"])
        self.assertEqual(payment.partner_id, payment.contact_id.partner_id)
        self.assertEqual(payment.buyer_email, self.contact_data["email"])
        self.assertFalse(payment.is_recurring)

    def test_recurring_payment(self):
        data = self._add(
            recurring={
                "is_recurring": True,
                "status": "active",
                "interval": "monthly",
                "subscription_id": "sub-123",
                "current_period_start": 1767225600,
                "current_period_end": 1769904000,
            }
        )
        self.sync()
        payment = self._payment(data)
        self.assertTrue(payment.is_recurring)
        self.assertEqual(payment.recurring_interval, "monthly")
        self.assertEqual(payment.recurring_status, "active")
        self.assertEqual(payment.subscription_id, "sub-123")
        self.assertEqual(payment.recurring_period_end, datetime.datetime(2026, 2, 1, 0, 0))

    def test_unknown_contact_built_from_buyer(self):
        late_contact = make_contact(email="late@example.com", first_name="Lee", last_name="Late")
        data = make_payment(late_contact, self.campaign_data)
        self.api.payments = [data]
        self.sync()
        payment = self._payment(data)
        self.assertEqual(payment.contact_id.zeffy_id, late_contact["id"])
        self.assertEqual(payment.partner_id.email, "late@example.com")
        self.assertEqual(payment.partner_id.name, "Lee Late")

    def test_payment_without_contact_matched_from_buyer(self):
        partner = self.Partner.create({"name": "Cash Giver", "email": "cash@example.com"})
        data = self._add(type="manual", payment_method={"type": "cash", "brand": None, "last4": None})
        data["contact"] = None
        data["buyer"]["email"] = "cash@example.com"
        self.sync()
        payment = self._payment(data)
        self.assertFalse(payment.contact_id)
        self.assertEqual(payment.partner_id, partner)
        self.assertEqual(payment.payment_type, "manual")
        self.assertEqual(payment.payment_method, "cash")

    def test_resync_updates_changed_payment_only(self):
        changed = self._add(receipt_url=None)
        same = self._add()
        self.sync()
        changed.update(
            refund_status="partial",
            receipt_url="https://receipts.example.com/late.pdf",
            refunds=[
                {"id": "r1", "object": "refund", "amount": 1000, "currency": "cad", "status": "succeeded", "created": 1767400000},
                {"id": "r2", "object": "refund", "amount": 500, "currency": "cad", "status": "failed", "created": 1767400000},
            ],
        )
        synced = []
        original = type(self.Payment)._zeffy_payment_synced

        def spy(records):
            synced.append(records)
            return original(records)

        with patch.object(type(self.Payment), "_zeffy_payment_synced", spy):
            self.sync()
        self.assertEqual(self.Payment.search_count([]), 2)
        payment = self._payment(changed)
        self.assertEqual(payment.refund_status, "partial")
        self.assertEqual(payment.refunded_amount, 10.0)
        self.assertEqual(payment.receipt_url, "https://receipts.example.com/late.pdf")
        touched = self.Payment.browse().union(*synced)
        self.assertEqual(touched, payment)
        self.assertNotIn(self._payment(same), touched)

    def test_hook_receives_created_payments(self):
        data = self._add()
        synced = []
        original = type(self.Payment)._zeffy_payment_synced

        def spy(records):
            synced.append(records)
            return original(records)

        with patch.object(type(self.Payment), "_zeffy_payment_synced", spy):
            self.sync()
        self.assertEqual(self.Payment.browse().union(*synced), self._payment(data))

    def test_deleted_payment_is_flagged_and_unflagged(self):
        kept = self._add()
        gone = self._add()
        self.sync()
        self.api.payments.remove(gone)
        self.sync()
        self.assertTrue(self._payment(gone).zeffy_deleted)
        self.assertFalse(self._payment(kept).zeffy_deleted)
        self.api.payments.append(gone)
        self.sync()
        self.assertFalse(self._payment(gone).zeffy_deleted)

    def test_failed_pass_flags_nothing(self):
        gone = self._add()
        self.sync()
        self.api.payments = []
        self.api.failures["payments"] = FakeResponse(
            500, {"error": {"code": "internal_error", "message": "down"}}
        )
        with self.assertRaises(ZeffyError):
            self.sync()
        self.assertFalse(self._payment(gone).zeffy_deleted)

    def test_companies_are_isolated(self):
        data = self._add()
        self.sync()
        other = self.env["res.company"].create({"name": "Other NPO", "zeffy_api_key": "test-key"})
        self.sync(other)
        payments = self.Payment.search([("zeffy_id", "=", data["id"])])
        self.assertEqual(payments.company_id, self.company | other)
        for payment in payments:
            self.assertEqual(payment.contact_id.company_id, payment.company_id)
            self.assertEqual(payment.campaign_id.company_id, payment.company_id)

    def test_failed_payments_are_synchronized(self):
        failed = self._add(status="failed")
        pending = self._add(status="pending")
        self.sync()
        self.assertEqual(self._payment(failed).status, "failed")
        pending["status"] = "failed"
        self.sync()
        payment = self._payment(pending)
        self.assertEqual(payment.status, "failed")
        self.assertFalse(payment.zeffy_deleted)
