# Acceptance criteria (task #3965, AC1):
#   AC-1: conversation.transport ships capability flags defaulting False and
#         abstract hooks that raise NotImplementedError on the base -- the
#         interface only, no hardcoded provider. One light assertion per the
#         design's test plan, not a suite (providers get the real coverage).
#   AC-5: browse_page/fetch_envelope are the RPC entry points the OWL inbox
#         client calls directly by transport id (conversation_inbox.js).
#         Their gating-on-browsable was covered for browse_page but not
#         fetch_envelope, and neither had a happy-path test showing they
#         actually delegate to the hooks -- covered here at the base-stub
#         level (with the hooks mocked out, since the base itself only
#         implements the dispatch/gating, not a real provider).

from unittest.mock import patch

from odoo.tests import TransactionCase


class TestConversationTransportInterface(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Bare Transport"}
        )

    def test_capability_flags_default_false(self):
        for flag in (
            "browsable",
            "searchable",
            "pushable",
            "sendable",
            "artifact_only",
        ):
            self.assertFalse(
                self.transport[flag], f"{flag} should default to False"
            )

    def test_abstract_hooks_raise_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            self.transport._browse()
        with self.assertRaises(NotImplementedError):
            self.transport._search_remote({})
        with self.assertRaises(NotImplementedError):
            self.transport._fetch("ext-1")
        with self.assertRaises(NotImplementedError):
            self.transport._normalize({})
        with self.assertRaises(NotImplementedError):
            self.transport._match_inbound({})
        with self.assertRaises(NotImplementedError):
            self.transport._send(self.env["mail.conversation"], self.env["mail.message"])
        with self.assertRaises(NotImplementedError):
            self.transport._subscribe_push()

    def test_browse_page_gated_on_browsable(self):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.transport.browse_page(self.transport.id)

    def test_browse_page_delegates_to_browse_when_browsable(self):
        browsable = self.env["conversation.transport"].create(
            {"name": "Browsable Transport", "browsable": True}
        )
        transport_model = type(browsable)
        with patch.object(
            transport_model, "_browse", return_value=[{"external_id": "1"}], autospec=True
        ) as mocked_browse:
            result = browsable.browse_page(browsable.id, query="foo", page=2)
        mocked_browse.assert_called_once_with(browsable, query="foo", page=2)
        self.assertEqual(result, [{"external_id": "1"}])

    def test_fetch_envelope_gated_on_browsable(self):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.transport.fetch_envelope(self.transport.id, "ext-1")

    def test_fetch_envelope_delegates_to_fetch_and_normalize(self):
        browsable = self.env["conversation.transport"].create(
            {"name": "Browsable Transport 2", "browsable": True}
        )
        transport_model = type(browsable)
        with patch.object(
            transport_model, "_fetch", return_value={"raw": True}, autospec=True
        ) as mocked_fetch, patch.object(
            transport_model,
            "_normalize",
            return_value={"subject": "Hi", "external_id": "ext-9"},
            autospec=True,
        ) as mocked_normalize:
            stub = browsable.fetch_envelope(browsable.id, "ext-9")
        mocked_fetch.assert_called_once_with(browsable, "ext-9")
        mocked_normalize.assert_called_once_with(browsable, {"raw": True})
        self.assertEqual(stub, {"subject": "Hi", "external_id": "ext-9"})
