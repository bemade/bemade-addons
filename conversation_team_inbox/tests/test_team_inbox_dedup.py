# Acceptance criteria (team inbox):
#   AC6  A message already delivered through the alias is recognised as
#        captured when the same mail is filed again from the inbox viewer,
#        by its RFC822 Message-Id (the IMAP UID is unknown for alias mail).

from odoo.tests import tagged

from .common import TeamInboxCommon


@tagged("post_install", "-at_install")
class TestTeamInboxDedup(TeamInboxCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Personal", "provider": False, "sendable": True}
        )

    def _stub(self, message_id, external_id="4711"):
        return {
            "subject": "Quote request",
            "body": "<p>Hello</p>",
            "email_from": "customer@client.example",
            "to": [self.alias_email],
            "cc": [],
            "external_id": external_id,
            "message_id": message_id,
        }

    def test_find_captured_by_message_id(self):
        conversation = self._inbound("<ti-d1@client.example>")
        find = self.Conversation._find_captured
        self.assertEqual(
            find(self.transport, "999", message_id="<ti-d1@client.example>"),
            conversation,
        )
        self.assertEqual(
            find(self.transport, "999", message_id="ti-d1@client.example"),
            conversation,
        )
        self.assertFalse(find(self.transport, "999", message_id="<unknown@x.example>"))
        self.assertFalse(find(self.transport, "999"))

    def test_capture_stub_does_not_file_a_delivered_mail_twice(self):
        conversation = self._inbound("<ti-d2@client.example>")
        before = self.Conversation.search_count([])
        messages = len(conversation.message_ids)
        captured = self.Conversation._capture_stub(
            self.transport, self._stub("<ti-d2@client.example>")
        )
        self.assertEqual(captured, conversation)
        self.assertEqual(self.Conversation.search_count([]), before)
        self.assertEqual(len(conversation.message_ids), messages)

    def test_capture_stub_unchanged_for_an_unknown_mail(self):
        before = self.Conversation.search_count([])
        captured = self.Conversation._capture_stub(
            self.transport, self._stub("<ti-d3@client.example>")
        )
        self.assertEqual(self.Conversation.search_count([]), before + 1)
        self.assertEqual(
            self.Conversation._find_captured(self.transport, "4711"), captured
        )
