# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Synthetic Zeffy API for the tests.

Payload shapes follow the official Zeffy OpenAPI schemas (Payment, Contact,
Campaign). All names, emails and addresses are invented.
"""

import itertools
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from ..models.zeffy_client import ZeffyClient

_seq = itertools.count(1)


def _uuid():
    return str(uuid.UUID(int=next(_seq)))


def make_campaign(**over):
    data = {
        "id": _uuid(),
        "object": "campaign",
        "created": 1767225600,
        "updated": 1767225600,
        "deleted_at": None,
        "type": "donation_form",
        "category": "DonationForm",
        "status": "active",
        "title": "Annual Campaign",
        "description": "",
        "locale": "fr",
        "url": "https://www.zeffy.com/fr-CA/donation-form/annual",
        "banner_url": None,
        "logo_url": None,
        "target": 1000000,
        "goal_amount": 1000000,
        "currency": "cad",
        "volume": 250000,
        "is_archived": False,
        "creator_user_id": None,
        "start_date": None,
        "end_date": None,
        "occurrences": [],
        "metadata": {},
    }
    data.update(over)
    return data


def make_address(**over):
    data = {
        "line1": "123 Rue Principale",
        "city": "Sainte-Exemple",
        "state": "QC",
        "postal_code": "J0A 1B0",
        "country": "CA",
    }
    data.update(over)
    return data


def make_contact(**over):
    data = {
        "id": _uuid(),
        "object": "contact",
        "created": 1767225600,
        "updated": 1767225600,
        "email": "alex.martin@example.com",
        "first_name": "Alex",
        "last_name": "Martin",
        "phone_number": "+15145550100",
        "address": make_address(),
        "donor_type": "OneTime",
        "total_contribution": 5000,
        "currency": "cad",
        "locale": "fr",
        "donation_count": 1,
        "first_donation_date": 1767225600,
        "last_donation_date": 1767225600,
        "metadata": {},
    }
    data.update(over)
    return data


def make_payment(contact=None, campaign=None, **over):
    contact = contact or make_contact()
    campaign = campaign or make_campaign()
    amount = over.pop("amount", 5000)
    data = {
        "id": _uuid(),
        "object": "payment",
        "created": 1767272400,  # 2026-01-01 13:00 UTC = 08:00 America/Toronto
        "amount": amount,
        "eligible_amount": amount,
        "currency": "cad",
        "status": "succeeded",
        "type": "online",
        "refund_status": "none",
        "refunds": [],
        "dispute": None,
        "description": campaign["title"],
        "contact": contact["id"],
        "payment_method": {"type": "card", "brand": "visa", "last4": "4242"},
        "buyer": {
            "email": contact["email"],
            "first_name": contact["first_name"],
            "last_name": contact["last_name"],
            "is_corporate": False,
            "company_name": None,
            "address": contact["address"],
        },
        "discount": None,
        "campaign_type": campaign["type"],
        "campaign_id": campaign["id"],
        "campaign_category": "donation",
        "buyer_questions": [],
        "items": [
            {
                "id": _uuid(),
                "object": "item",
                "type": "donation",
                "amount": amount,
                "currency": "cad",
                "recurrence_interval": "oneTime",
                "rate_id": None,
                "rate_title": None,
                "parent_rate_id": None,
                "parent_rate_title": None,
                "contact_id": None,
                "questions": [],
                "tribute": None,
            }
        ],
        "occurrence_id": None,
        "receipt_url": "https://receipts.example.com/receipt-0001.pdf",
        "recurring": None,
        "fund": None,
        "metadata": {},
    }
    data.update(over)
    return data


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


class FakeZeffyApi:
    """In-memory stand-in for api.zeffy.com, newest-first lists, cursor
    pagination on ``starting_after``, ``created``/``updated`` filters, and
    failed payments omitted unless ``status=failed`` is asked for."""

    def __init__(self, api_key="test-key"):
        self.api_key = api_key
        self.campaigns = []
        self.contacts = []
        self.payments = []
        self.calls = []
        # Queue of FakeResponse to return before serving normally (e.g. 429s).
        self.queued = []
        # path -> FakeResponse returned for every call to that resource.
        self.failures = {}

    def request(self, client, path, params=None):
        params = dict(params or {})
        self.calls.append((path, params))
        if self.queued:
            return self.queued.pop(0)
        if client.api_key != self.api_key:
            return FakeResponse(
                401,
                {
                    "error": {
                        "type": "authentication_error",
                        "code": "invalid_api_key",
                        "message": "Invalid API key.",
                        "status": 401,
                    }
                },
            )
        if path in self.failures:
            return self.failures[path]
        items = list(getattr(self, path))
        if path == "payments":
            # Like Zeffy: failed payments are only listed when asked for.
            wanted = params.get("status")
            items = [r for r in items if (r["status"] == wanted if wanted else r["status"] != "failed")]
        items.sort(key=lambda r: r["created"], reverse=True)
        for key, value in params.items():
            for field in ("created", "updated"):
                if key == f"{field}[gte]":
                    items = [r for r in items if r[field] >= int(value)]
        after = params.get("starting_after")
        if after:
            ids = [r["id"] for r in items]
            items = items[ids.index(after) + 1 :]
        limit = int(params.get("limit", 10))
        page = items[:limit]
        has_more = len(items) > limit
        return FakeResponse(
            200,
            {
                "object": "list",
                "data": page,
                "has_more": has_more,
                "next_cursor": page[-1]["id"] if has_more else None,
            },
        )

    @contextmanager
    def patched(self):
        api = self

        def _request(client, path, params=None):
            return api.request(client, path, params)

        with patch.object(ZeffyClient, "_request", _request):
            yield self


class ZeffyCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.zeffy_api_key = "test-key"
        cls.cad = cls.env.ref("base.CAD")
        cls.cad.active = True
        cls.quebec = cls.env.ref("base.state_ca_qc")
        cls.Campaign = cls.env["zeffy.campaign"]
        cls.Contact = cls.env["zeffy.contact"]
        cls.Payment = cls.env["zeffy.payment"]
        cls.Partner = cls.env["res.partner"]

    def setUp(self):
        super().setUp()
        self.api = FakeZeffyApi()
        self.enterContext(self.api.patched())

    def sync(self, company=None):
        return (company or self.company)._zeffy_sync()
