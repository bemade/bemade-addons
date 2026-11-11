# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Use case: talk to the Zeffy API reliably.

Acceptance criteria
- A list endpoint is read to the end by following ``next_cursor`` through
  ``starting_after``, 100 records per page.
- A 429 answer is retried after the ``Retry-After`` delay; after too many
  429s the client gives up with an error instead of looping forever.
- An invalid key raises ``ZeffyAuthError``; any other error answer raises
  ``ZeffyError`` carrying Zeffy's message.
- The client never issues anything but GET requests (read-only).
"""

from unittest.mock import patch

from odoo.tests import tagged

from ..models.zeffy_client import ZeffyAuthError, ZeffyClient, ZeffyError
from .common import FakeResponse, ZeffyCase, make_campaign

# Captured before any test patches the transport.
_REAL_REQUEST = ZeffyClient._request


@tagged("post_install", "-at_install")
class TestZeffyClient(ZeffyCase):
    def _client(self, key="test-key"):
        return ZeffyClient(key, sleep=self.sleeps.append)

    def setUp(self):
        super().setUp()
        self.sleeps = []

    def test_iter_list_follows_cursor_to_the_end(self):
        self.api.campaigns = [
            make_campaign(created=1767225600 + i) for i in range(250)
        ]
        ids = [c["id"] for c in self._client().iter_list("campaigns")]
        self.assertEqual(len(ids), 250)
        self.assertEqual(len(set(ids)), 250)
        self.assertEqual(len(self.api.calls), 3)
        self.assertTrue(all(p["limit"] == 100 for _path, p in self.api.calls))
        self.assertNotIn("starting_after", self.api.calls[0][1])
        self.assertIn("starting_after", self.api.calls[1][1])

    def test_rate_limit_is_retried_after_delay(self):
        self.api.campaigns = [make_campaign()]
        self.api.queued = [
            FakeResponse(429, {"error": {"code": "rate_limit_exceeded"}}, {"Retry-After": "1"})
        ]
        result = list(self._client().iter_list("campaigns"))
        self.assertEqual(len(result), 1)
        self.assertEqual(self.sleeps, [1.0])

    def test_rate_limit_gives_up_eventually(self):
        self.api.queued = [
            FakeResponse(429, {"error": {"code": "rate_limit_exceeded"}}, {"Retry-After": "1"})
            for _i in range(10)
        ]
        with self.assertRaises(ZeffyError):
            list(self._client().iter_list("campaigns"))

    def test_invalid_key_raises_auth_error(self):
        with self.assertRaises(ZeffyAuthError):
            self._client("wrong-key").test_connection()

    def test_error_answer_carries_zeffy_message(self):
        self.api.failures["payments"] = FakeResponse(
            500,
            {"error": {"type": "api_error", "code": "internal_error", "message": "Boom upstream"}},
        )
        with self.assertRaisesRegex(ZeffyError, "Boom upstream"):
            list(self._client().iter_list("payments"))

    def test_only_get_requests_are_issued(self):
        """The real transport: only requests.get is ever used."""
        with (
            patch.object(ZeffyClient, "_request", _REAL_REQUEST),
            patch(
                "odoo.addons.zeffy_connector.models.zeffy_client.requests"
            ) as requests_mock,
        ):
            requests_mock.get.return_value = FakeResponse(
                200, {"object": "list", "data": [], "has_more": False}
            )
            self._client().test_connection()
        args, kwargs = requests_mock.get.call_args
        self.assertEqual(args[0], "https://api.zeffy.com/api/v1/campaigns")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        for verb in ("post", "put", "patch", "delete", "request"):
            self.assertFalse(getattr(requests_mock, verb).called, verb)
