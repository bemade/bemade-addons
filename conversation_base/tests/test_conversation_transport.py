# Acceptance criteria (task #3965, AC1):
#   AC-1: conversation.transport ships capability flags defaulting False and
#         abstract hooks that raise NotImplementedError on the base -- the
#         interface only, no hardcoded provider. One light assertion per the
#         design's test plan, not a suite (providers get the real coverage).

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
