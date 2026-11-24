"""Ticket emails: the signature shows the ticket team's address.

Acceptance criteria:
- An internal user's reply on a ticket: the signature shows the team's
  signature email address instead of the user's personal address, whoever
  writes (it wins over the user's own setting).
- From and Reply-To are the same as without the addon setting.
- Team signature address empty: the team's own alias.
- A team without any inbox: the user's own rule applies.
- Messages authored by the customer are left untouched.
"""

from markupsafe import Markup

from odoo import Command
from odoo.tests import tagged

from odoo.addons.mail.tests.common import MailCommon


@tagged("post_install", "-at_install")
class TestTicketSignature(MailCommon):
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
                "signature": '<p>Desk Agent</p><p><a href="mailto:desk.agent@example.com">'
                "desk.agent@example.com</a></p>",
            }
        )
        cls.agent_sendas = cls.env["res.users"].create(
            {
                "name": "Desk Buyer",
                "login": "desk_buyer",
                "email": "desk.buyer@example.com",
                "group_ids": [Command.set(groups)],
                "signature": "<p>Desk Buyer - Desk.Buyer@Example.com</p>",
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
        cls.sac_email = "sac-test@%s" % cls.alias_domain
        cls.care_email = "care-test@%s" % cls.alias_domain
        cls.buying_email = "buying-test@%s" % cls.alias_domain
        cls.agent_sendas.mail_send_as_alias_id = cls.other_team.alias_id
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

    def test_from_and_reply_to_unchanged(self):
        before, before_mail = self._reply(self.agent)
        self.team.mail_send_as_alias_id = self.sac_alias
        after, after_mail = self._reply(self.agent)
        self.assertEqual(after.email_from, self.agent.email_formatted)
        self.assertEqual(after.email_from, before.email_from)
        self.assertEqual(after.reply_to, before.reply_to)
        self.assertEqual(after_mail.email_from, before_mail.email_from)
        self.assertEqual(after_mail.reply_to, before_mail.reply_to)
        self.assertNotIn(self.sac_email, after_mail.reply_to or "")

    def test_agent_signature_shows_team_address(self):
        self.team.mail_send_as_alias_id = self.sac_alias
        _message, mail = self._reply(self.agent)
        self.assertIn('href="mailto:%s"' % self.sac_email, mail.body_html)
        self.assertIn(">%s</a>" % self.sac_email, mail.body_html)
        self.assertNotIn("mailto:desk.agent@example.com", mail.body_html)
        self.assertIn("desk.agent@example.com", self.agent.signature)

    def test_team_address_wins_over_user_setting(self):
        self.team.mail_send_as_alias_id = self.sac_alias
        _message, mail = self._reply(self.agent_sendas)
        self.assertIn("Desk Buyer - %s" % self.sac_email, mail.body_html)
        self.assertNotIn(self.buying_email, mail.body_html)

    def test_team_address_empty_uses_team_alias(self):
        self.team.mail_send_as_alias_id = False
        _message, mail = self._reply(self.agent)
        self.assertIn('href="mailto:%s"' % self.care_email, mail.body_html)

    def test_team_without_inbox_falls_back_on_user_rule(self):
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "Quiet ticket", "team_id": self.no_alias_team.id, "partner_id": self.customer.id}
        )
        _message, mail = self._reply(self.agent_sendas, ticket=ticket)
        self.assertIn("Desk Buyer - %s" % self.buying_email, mail.body_html)
        _message, mail = self._reply(self.agent, ticket=ticket)
        self.assertIn('href="mailto:desk.agent@example.com"', mail.body_html)

    def test_customer_message_untouched(self):
        body = Markup(
            '<p>My machine is down.</p><div data-o-mail-quote="1">-- <br>'
            "<p>desk.customer@example.com</p></div>"
        )
        message = self.ticket.message_post(
            body=body,
            author_id=self.customer.id,
            email_from=self.customer.email_formatted,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.assertEqual(message.email_from, self.customer.email_formatted)
        self.assertIn("desk.customer@example.com", message.body)
        self.assertNotIn(self.care_email, message.body)
