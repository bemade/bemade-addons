# Acceptance criteria (team inbox):
#   AC4  Replying from an alias-created conversation sends through the team
#        transport, from the team address, via the mail server Odoo finds
#        for it; with no from address the reply raises.
#   AC5  The reply keeps its RFC822 Message-Id, so the customer's answer
#        threads back into the same conversation through the gateway.
#   AC8  Full path: raw RFC822 in -> action_reply out -> customer reply in.

from email import message_from_string

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TeamInboxCommon


@tagged("post_install", "-at_install")
class TestTeamInboxSend(TeamInboxCommon):
    def _sent_message(self):
        self.assertEqual(len(self.emails), 1, self.emails)
        return message_from_string(self.emails[0]["message"])

    def test_reply_goes_out_from_the_team_address(self):
        conversation = self._inbound(
            "<ti-s1@client.example>", cc="watcher@client.example"
        )
        with self.mock_smtplib_connection():
            message = conversation.action_reply("<p>Here is the quote.</p>")

        self.assertEqual(len(self.emails), 1)
        self.assertEqual(self.emails[0]["smtp_from"], "sales@team.example.com")
        # exactly the customer: never the team's own alias, never the Cc.
        self.assertEqual(self.emails[0]["smtp_to_list"], ["customer@client.example"])
        sent = self._sent_message()
        self.assertEqual(sent["From"], "sales@team.example.com")
        self.assertEqual(sent["Reply-To"], "sales@team.example.com")
        self.assertEqual(sent["Message-Id"], message.message_id)
        self.assertEqual(sent["In-Reply-To"], "<ti-s1@client.example>")
        self.assertEqual(message.transport_id, self.team.team_transport_id)
        self.assertEqual(message.external_id, message.message_id.strip("<>"))
        self.assertTrue(
            self.find_mail_server_mocked.call_args_list,
            "the send must go through ir.mail_server._find_mail_server",
        )
        self.assertEqual(
            self.connect_mocked.call_args.kwargs.get("mail_server_id"),
            self.team_server.id,
        )

    def test_reply_to_all_excludes_the_team_itself(self):
        conversation = self._inbound(
            "<ti-s2@client.example>", cc="watcher@client.example"
        )
        with self.mock_smtplib_connection():
            conversation.action_reply(
                "<p>Hi all</p>",
                recipients=conversation._all_participant_emails(),
            )
        self.assertEqual(
            sorted(self.emails[0]["smtp_to_list"]),
            ["customer@client.example", "watcher@client.example"],
        )

    def test_reply_without_from_address_raises(self):
        conversation = self._inbound("<ti-s3@client.example>")
        self.team.from_address = False
        with self.assertRaisesRegex(UserError, "no from address configured"):
            conversation.action_reply("<p>Hello</p>")

    def test_customer_reply_threads_into_the_same_conversation(self):
        conversation = self._inbound("<ti-s4@client.example>")
        with self.mock_smtplib_connection():
            reply = conversation.action_reply("<p>Quote attached.</p>")
        count = self.env["mail.conversation"].search_count([])

        again = self._inbound(
            "<ti-s4-answer@client.example>",
            subject="Re: Quote request",
            in_reply_to=reply.message_id,
        )
        self.assertEqual(again, conversation)
        self.assertEqual(self.env["mail.conversation"].search_count([]), count)
        self.assertIn(
            "<ti-s4-answer@client.example>", conversation.message_ids.mapped("message_id")
        )

        other = self._inbound("<ti-s4-other@client.example>", subject="Something else")
        self.assertNotEqual(other, conversation)
        self.assertEqual(self.env["mail.conversation"].search_count([]), count + 1)

    def test_second_reply_answers_the_latest_customer_message(self):
        conversation = self._inbound("<ti-s5@client.example>")
        with self.mock_smtplib_connection():
            first = conversation.action_reply("<p>One</p>")
        self._inbound(
            "<ti-s5b@client.example>", subject="Re: Quote request", in_reply_to=first.message_id
        )
        self.emails = []
        with self.mock_smtplib_connection():
            conversation.action_reply("<p>Two</p>")
        self.assertEqual(self._sent_message()["In-Reply-To"], "<ti-s5b@client.example>")
