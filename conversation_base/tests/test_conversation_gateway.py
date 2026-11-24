# Acceptance criteria (task #3965):
#   AC-9 (test plan #5, gateway backbone): inbound mail to a mail.conversation
#     alias creates a conversation with participants-not-followers via
#     message_new; a follow-up whose References match threads into the SAME
#     conversation (no second conversation created). Correlation stays
#     within a transport (auto-correlation by References/In-Reply-To for
#     email); the base mail.thread gateway machinery provides the threading,
#     our message_new override only adds participant hygiene on top.

from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestConversationGateway(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        conversation_model = cls.env["ir.model"]._get("mail.conversation")
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "conv-inbox-test",
                "alias_model_id": conversation_model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)

    def _inbound(self, msg_id, in_reply_to=None, to=None, cc="watcher@example.com"):
        headers = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\n"
            "Subject: Question about my order\n"
            "From: Gateway Customer <gateway_customer@example.com>\n"
            "To: %s\n"
            "%s"
        ) % (msg_id, to or self.alias_email, "Cc: %s\n" % cc if cc else "")
        if in_reply_to:
            headers += "In-Reply-To: %s\n" % in_reply_to
        mime = (
            headers
            + 'Content-Type: text/plain; charset="UTF-8"\n'
            + "\n"
            + "Hello, I have a question.\n"
        )
        return self.env["mail.thread"].sudo().message_process(False, mime)

    def test_inbound_creates_conversation_with_participants_not_followers(self):
        conversation_id = self._inbound("<gw-msg-1@example.com>")
        conversation = self.env["mail.conversation"].browse(conversation_id)

        self.assertTrue(conversation)
        self.assertFalse(conversation.message_follower_ids)

        emails = set(conversation.participant_ids.mapped("email_normalized"))
        self.assertIn("gateway_customer@example.com", emails)
        self.assertIn("watcher@example.com", emails)

        requester = conversation.participant_ids.filtered(
            lambda p: p.email_normalized == "gateway_customer@example.com"
        )
        self.assertEqual(requester.role, "requester")

    def test_reply_with_matching_references_threads_into_same_conversation(self):
        before_count = self.env["mail.conversation"].search_count([])

        conversation_id = self._inbound("<gw-msg-2@example.com>")
        self.assertTrue(conversation_id)
        self.assertEqual(
            self.env["mail.conversation"].search_count([]), before_count + 1
        )

        # a follow-up In-Reply-To the first message must NOT create a
        # second conversation.
        second_id = self._inbound(
            "<gw-msg-2-reply@example.com>", in_reply_to="<gw-msg-2@example.com>"
        )
        self.assertEqual(
            second_id,
            conversation_id,
            "a reply matching In-Reply-To should thread into the same "
            "conversation, not create a second one",
        )
        self.assertEqual(
            self.env["mail.conversation"].search_count([]),
            before_count + 1,
            "no second conversation created for a correlated reply",
        )

    def _participants(self, conversation_id):
        conversation = self.env["mail.conversation"].browse(conversation_id)
        return {
            p.email_normalized: p.role for p in conversation.participant_ids
        }

    def test_team_address_is_not_a_participant_among_outside_addresses(self):
        conversation_id = self._inbound(
            "<gw-own-1@example.com>",
            to="%s, Ann <ann@example.org>, bob@example.net" % self.alias_email,
            cc=False,
        )
        self.assertEqual(
            self._participants(conversation_id),
            {
                "gateway_customer@example.com": "requester",
                "ann@example.org": "to",
                "bob@example.net": "to",
            },
        )

    def test_team_address_in_cc_is_not_a_participant(self):
        conversation_id = self._inbound(
            "<gw-own-2@example.com>",
            to="ann@example.org",
            cc="%s, watcher@example.com" % self.alias_email,
        )
        self.assertEqual(
            self._participants(conversation_id),
            {
                "gateway_customer@example.com": "requester",
                "ann@example.org": "to",
                "watcher@example.com": "cc",
            },
        )

    def test_mail_to_the_team_alone_only_has_the_sender(self):
        conversation_id = self._inbound("<gw-own-3@example.com>", cc=False)
        self.assertEqual(
            self._participants(conversation_id),
            {"gateway_customer@example.com": "requester"},
        )

    def test_filtered_keys_win_when_present_even_if_empty(self):
        conversation = self.env["mail.conversation"].create({"name": "Hand built"})
        conversation._sync_participants_from_msg_dict(
            {
                "email_from": "sender@example.com",
                "to": self.alias_email,
                "cc": "cc-raw@example.com",
                "to_filtered": "",
                "cc_filtered": "",
            }
        )
        self.assertEqual(
            {p.email_normalized: p.role for p in conversation.participant_ids},
            {"sender@example.com": "requester"},
        )

    def test_raw_values_used_when_filtered_keys_are_absent(self):
        conversation = self.env["mail.conversation"].create({"name": "Hand built"})
        conversation._sync_participants_from_msg_dict(
            {
                "email_from": "sender@example.com",
                "to": "ann@example.org",
                "cc": "cc-raw@example.com",
            }
        )
        self.assertEqual(
            {p.email_normalized: p.role for p in conversation.participant_ids},
            {
                "sender@example.com": "requester",
                "ann@example.org": "to",
                "cc-raw@example.com": "cc",
            },
        )

    def test_route_via_alias_drops_the_team_address(self):
        raw = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: <gw-own-4@example.com>\n"
            "Subject: Routed\n"
            "From: Gateway Customer <gateway_customer@example.com>\n"
            "To: %s, ann@example.org\n"
            'Content-Type: text/plain; charset="UTF-8"\n\nHello\n'
        ) % self.alias_email
        conversation = (
            self.env["mail.conversation"].sudo()._route_via_alias(raw)
        )
        self.assertEqual(
            {p.email_normalized: p.role for p in conversation.participant_ids},
            {"gateway_customer@example.com": "requester", "ann@example.org": "to"},
        )
