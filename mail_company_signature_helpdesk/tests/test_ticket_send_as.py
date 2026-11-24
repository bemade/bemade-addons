"""Ticket emails go out from the ticket team's inbox.

Acceptance criteria:
- A reply on a ticket by an internal user WITHOUT "Send emails as" goes out
  as "User Name (Team)" <team send-as inbox>, Reply-To the same.
- A user WITH their own, different send-as: the team's inbox wins.
- Team "Send as" empty: the team's own alias.
- A message authored by the customer is left untouched.
- A team without any inbox: the user's own rule applies.
- The customer's reply to that inbox (In-Reply-To) lands on the same ticket.
"""

from odoo import Command
from odoo.tests import tagged
from odoo.tools import formataddr

from odoo.addons.mail.tests.common import MailCommon

REPLY_TEMPLATE = """Return-Path: {return_path}
To: {to}
cc: {cc}
From: {email_from}
Subject: {subject}
MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Date: {date}
Message-ID: {msg_id}
{extra}
Thanks, it works now.
"""


@tagged("post_install", "-at_install")
class TestTicketSendAs(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        groups = (
            cls.env.ref("base.group_user") | cls.env.ref("helpdesk.group_helpdesk_user")
        ).ids
        cls.agent = cls.env["res.users"].create(
            {
                "name": "Desk Agent",
                "login": "desk_agent",
                "email": "desk.agent@example.com",
                "group_ids": [Command.set(groups)],
            }
        )
        cls.agent_sendas = cls.env["res.users"].create(
            {
                "name": "Desk Buyer",
                "login": "desk_buyer",
                "email": "desk.buyer@example.com",
                "group_ids": [Command.set(groups)],
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Desk Customer", "email": "desk.customer@example.com"}
        )
        Team = cls.env["helpdesk.team"].with_context(mail_create_nosubscribe=True)
        cls.team = Team.create(
            {
                "name": "Care Test",
                "use_alias": True,
                "alias_name": "care-test",
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.other_team = Team.create(
            {
                "name": "Buying Test",
                "use_alias": True,
                "alias_name": "buying-test",
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.no_alias_team = Team.create({"name": "Quiet Test", "use_alias": False})
        cls.no_alias_team.alias_name = False
        IrModel = cls.env["ir.model"]
        cls.sac_alias = cls.env["mail.alias"].create(
            {
                "alias_name": "sac-test",
                "alias_domain_id": cls.mail_alias_domain.id,
                "alias_model_id": IrModel._get_id("helpdesk.ticket"),
                "alias_parent_model_id": IrModel._get_id("helpdesk.team"),
                "alias_parent_thread_id": cls.team.id,
                "alias_defaults": "{'team_id': %s}" % cls.team.id,
            }
        )
        cls.team.mail_send_as_alias_id = cls.sac_alias
        cls.agent_sendas.mail_send_as_alias_id = cls.other_team.alias_id
        cls.sac_email = "sac-test@%s" % cls.alias_domain
        cls.ticket = cls.env["helpdesk.ticket"].create(
            {"name": "Desk ticket", "team_id": cls.team.id, "partner_id": cls.customer.id}
        )

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _reply(self, user, ticket=None, **kwargs):
        ticket = ticket or self.ticket
        with self.mock_mail_gateway():
            message = ticket.with_user(user).message_post(
                body="We are on it.",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.customer.ids,
                **kwargs,
            )
            self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.customer in m.recipient_ids)
        self.assertEqual(len(mail), 1)
        return message, mail

    def test_agent_without_send_as_uses_team_inbox(self):
        message, mail = self._reply(self.agent)
        expected = formataddr(("Desk Agent (Care Test)", self.sac_email))
        self.assertEqual(message.email_from, expected)
        self.assertEqual(message.reply_to, expected)
        self.assertEqual(mail.email_from, expected)
        self.assertEqual(mail.reply_to, expected)

    def test_team_inbox_wins_over_user_send_as(self):
        message, mail = self._reply(self.agent_sendas)
        expected = formataddr(("Desk Buyer (Care Test)", self.sac_email))
        self.assertEqual(message.email_from, expected)
        self.assertEqual(mail.reply_to, expected)

    def test_team_send_as_empty_uses_team_alias(self):
        self.team.mail_send_as_alias_id = False
        message, _mail = self._reply(self.agent)
        self.assertEqual(
            message.email_from,
            formataddr(("Desk Agent (Care Test)", "care-test@%s" % self.alias_domain)),
        )

    def test_customer_message_untouched(self):
        message = self.ticket.message_post(
            body="My machine is down.",
            author_id=self.customer.id,
            email_from=self.customer.email_formatted,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.assertEqual(message.email_from, self.customer.email_formatted)

    def test_team_without_inbox_falls_back_on_user_rule(self):
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "Quiet ticket", "team_id": self.no_alias_team.id, "partner_id": self.customer.id}
        )
        message, _mail = self._reply(self.agent_sendas, ticket=ticket)
        self.assertEqual(
            message.email_from,
            formataddr(("Desk Buyer (Buying Test)", "buying-test@%s" % self.alias_domain)),
        )
        message, _mail = self._reply(self.agent, ticket=ticket)
        self.assertEqual(message.email_from, self.agent.email_formatted)

    def test_customer_reply_lands_on_ticket(self):
        message, _mail = self._reply(self.agent)
        self.format_and_process(
            REPLY_TEMPLATE,
            self.customer.email_formatted,
            self.sac_email,
            subject="Re: Desk ticket",
            extra="In-Reply-To: %s\nReferences: %s\n" % (message.message_id, message.message_id),
            target_model="helpdesk.ticket",
        )
        self.assertEqual(
            self.env["helpdesk.ticket"].search_count([("name", "=", "Re: Desk ticket")]), 0
        )
        reply = self.ticket.message_ids.filtered(lambda m: m.subject == "Re: Desk ticket")
        self.assertEqual(len(reply), 1)
        self.assertEqual(reply.parent_id, message)
