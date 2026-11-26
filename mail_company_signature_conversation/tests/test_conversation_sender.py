"""Use case: « Send from the signature address » and Conversations replies.

Acceptance criteria:
- AC1: option on, a user whose sending address is a team alias: a reply sent
  from their personal mailbox records that mailbox (their name, its login); a
  reply over their own team's transport and over another team's transport
  record that transport's login. None is recorded under the team alias.
- AC2: forwards and messages recorded after sending (_record_outbound) record
  the transport's sender too.
- AC3: the quote of a reply and the header of a forward show that sender
  (when conversation_draft / conversation_forward are installed).
- AC4: option off: nothing changes. A message that is not a conversation post
  keeps the rewrite; an internal note on a conversation is left alone.
"""

from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import email_normalize

from odoo.addons.mail_company_signature.tests.common_sender import SenderCommon


@tagged("post_install", "-at_install")
class TestConversationSender(SenderCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Transport = cls.env["conversation.transport"]
        cls.user = cls.u_full
        cls.personal = Transport.create(
            {
                "name": "Personal",
                "sendable": True,
                "user_id": cls.user.id,
                "login": "personal.box@example.com",
            }
        )
        cls.own_team = Transport.create(
            {"name": "Own team", "sendable": True, "login": "sac@example.com"}
        )
        cls.other_team = Transport.create(
            {"name": "Other team", "sendable": True, "login": "billing@example.com"}
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Quote request", "primary_transport_id": cls.personal.id}
        )
        # The user's sending address is a team alias, as in production.
        cls.user.sudo().mail_send_as_alias_id = cls.alias
        cls.env.flush_all()

    def _reply(self, transport):
        conversation = self.conversation.with_user(self.user)
        with patch.object(
            type(transport), "_send", return_value="ext-1", autospec=True
        ):
            return conversation.action_reply(
                "<p>Bonjour</p>",
                recipients=["customer@example.com"],
                transport=transport.with_user(self.user),
            ).sudo()

    def test_ac1_reply_records_the_mailbox_it_was_sent_from(self):
        self._setting()
        message = self._reply(self.personal)
        self.assertEqual(
            email_normalize(message.email_from), "personal.box@example.com"
        )
        self.assertIn(self.user.name, message.email_from)
        self.assertNotIn(self.alias_email, message.email_from)

        for transport, login in (
            (self.own_team, "sac@example.com"),
            (self.other_team, "billing@example.com"),
        ):
            message = self._reply(transport)
            self.assertEqual(message.email_from, login)
            self.assertEqual(message.author_id, self.user.partner_id)

    def test_ac2_forward_and_recorded_outbound(self):
        self._setting()
        conversation = self.conversation.with_user(self.user)
        with patch.object(
            type(self.own_team), "_send", return_value="ext-2", autospec=True
        ):
            forwarded = conversation.action_forward(
                "<p>FYI</p>", ["colleague@example.com"], transport=self.own_team
            ).sudo()
        self.assertEqual(forwarded.email_from, "sac@example.com")
        recorded = conversation._record_outbound(
            self.personal, "Re: Quote", "<p>Done</p>", "<abc@example.com>"
        ).sudo()
        self.assertEqual(
            email_normalize(recorded.email_from), "personal.box@example.com"
        )

    def test_ac3_quote_and_forward_header_show_the_sender(self):
        self._setting()
        message = self._reply(self.own_team)
        if "mail.conversation.draft" in self.env:
            draft = self.env["mail.conversation.draft"].new(
                {"conversation_id": self.conversation.id}
            )
            self.assertIn("sac@example.com", str(draft._quote_of(message)))
        if hasattr(self.conversation, "_forward_body"):
            body = self.conversation._forward_body(message)
            self.assertIn("sac@example.com", str(body))
            self.assertNotIn(self.alias_email, str(body))

    def test_ac4_option_off_unchanged(self):
        message = self._reply(self.personal)
        self.assertEqual(message.email_from, self.user.email_formatted)
        message = self._reply(self.own_team)
        self.assertEqual(message.email_from, self.user.email_formatted)

    def test_ac4_other_messages_keep_the_rewrite(self):
        self._setting()
        document, _mail = self._post(self.user)
        self.assertEqual(
            document.email_from,
            '"Sig sig_full (Purchasing Team)" <%s>' % self.alias_email,
        )
        # A note on a conversation is not sent anywhere: its author stays.
        note = (
            self.conversation.with_user(self.user)
            .message_post(body="<p>Note</p>", subtype_xmlid="mail.mt_note")
            .sudo()
        )
        self.assertEqual(note.email_from, self.user.email_formatted)
