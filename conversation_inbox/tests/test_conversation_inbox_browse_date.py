# Acceptance criteria:
#   - browse_page hands the viewer every message date as the same instant in
#     naive UTC (the web client treats serialized datetimes as UTC), whatever
#     offset the Date header carried.
#   - A missing date stays False, strings and naive values pass through, and
#     the stubs the engine caches are not mutated.

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from odoo.tests import TransactionCase


class TestConversationInboxBrowseDate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Date Transport", "browsable": True}
        )

    def _browse(self, dates):
        stubs = [
            {"external_id": str(i), "subject": "s", "date": d}
            for i, d in enumerate(dates)
        ]
        payload = {"items": stubs, "page": 1, "page_size": 10, "has_more": False}
        cls = type(self.transport)
        with patch.object(cls, "_browse", lambda self, query=None, page=1: payload):
            result = self.env["conversation.transport"].browse_page(self.transport.id)
        return stubs, result

    def test_foreign_offsets_become_the_same_instant_in_utc(self):
        def at(hours):
            return datetime(
                2026, 11, 1, 18, 10, 20, tzinfo=timezone(timedelta(hours=hours))
            )

        _stubs, result = self._browse([at(-5), at(1), at(-8), at(0)])
        self.assertEqual(
            [item["date"] for item in result["items"]],
            [
                datetime(2026, 11, 1, 23, 10, 20),
                datetime(2026, 11, 1, 17, 10, 20),
                datetime(2026, 11, 2, 2, 10, 20),
                datetime(2026, 11, 1, 18, 10, 20),
            ],
        )
        self.assertEqual(result["page"], 1)
        self.assertFalse(result["has_more"])

    def test_missing_and_plain_dates_pass_through_without_mutating_stubs(self):
        aware = datetime(2026, 11, 1, 18, 10, 20, tzinfo=timezone(timedelta(hours=-5)))
        naive = datetime(2026, 11, 1, 18, 10, 20)
        stubs, result = self._browse([False, "2026-08-14 09:00:00", naive, aware])
        self.assertEqual(
            [item["date"] for item in result["items"]],
            [False, "2026-08-14 09:00:00", naive, datetime(2026, 11, 1, 23, 10, 20)],
        )
        # The engine's cached stub still carries the aware datetime.
        self.assertIs(stubs[3]["date"], aware)
