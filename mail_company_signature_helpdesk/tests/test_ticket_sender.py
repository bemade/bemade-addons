"""Use case: ticket emails use the ticket team's address, whoever writes.

Acceptance criteria (company signature policy on):
- AC1: an agent's reply on a ticket: the signature shows the team's sending
  address, not the agent's; From / Reply-To as without the addon while the
  setting « Send from the signature address » is off.
- AC2: the team address wins over the agent's own sending address.
- AC3: team sending address empty: the team's own alias.
- AC4: a team without an inbox: the agent's own rule applies.
- AC5: setting on: From « Agent (Team) » <team address>, Reply-To the team
  address.
- AC6: messages authored by the customer are left untouched.
- AC7: the composer preview data of a ticket is the signature built for it.
"""

from odoo.tests import tagged
from odoo.tools import email_normalize

from odoo.addons.mail.tools.discuss import Store

from .common import TicketSenderCommon


@tagged("post_install", "-at_install")
class TestTicketSender(TicketSenderCommon):
    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _reply(self, user, ticket=None):
        ticket = ticket or self.ticket
        with self.mock_mail_gateway():
            message = ticket.with_user(user).message_post(
                body="We are on it.",
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                partner_ids=self.customer.ids,
            )
            self.env.flush_all()
        mail = self._new_mails.filtered(lambda m: self.customer in m.recipient_ids)
        self.assertEqual(len(mail), 1)
        return message, mail

    @staticmethod
    def _signature_part(html):
        html = str(html)
        start = html.find("Conseiller")
        return html[start:] if start >= 0 else ""

    def test_ac1_signature_team_address_from_unchanged(self):
        before, before_mail = self._reply(self.agent)
        self._enable_policy()
        self.team.mail_send_as_alias_id = self.sac_alias
        after, after_mail = self._reply(self.agent)
        signature = self._signature_part(after_mail.body_html)
        self.assertIn("Courriel : %s" % self.sac_email, signature)
        self.assertNotIn("desk.agent@example.com", signature)
        self.assertEqual(after.email_from, before.email_from)
        self.assertEqual(after.reply_to, before.reply_to)
        self.assertEqual(after_mail.email_from, before_mail.email_from)
        self.assertIn("desk.agent@example.com", self.agent.signature, "stored signature unchanged")

    def test_ac2_team_wins_over_user(self):
        self._enable_policy()
        self.team.mail_send_as_alias_id = self.sac_alias
        _message, mail = self._reply(self.agent_sendas)
        signature = self._signature_part(mail.body_html)
        self.assertIn("Courriel : %s" % self.sac_email, signature)
        self.assertNotIn(self.buying_email, signature)

    def test_ac3_empty_uses_team_alias(self):
        self._enable_policy()
        _message, mail = self._reply(self.agent)
        self.assertIn("Courriel : %s" % self.care_email, self._signature_part(mail.body_html))

    def test_ac4_team_without_inbox(self):
        self._enable_policy()
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "Quiet ticket", "team_id": self.no_alias_team.id, "partner_id": self.customer.id}
        )
        _message, mail = self._reply(self.agent_sendas, ticket=ticket)
        self.assertIn("Courriel : %s" % self.buying_email, self._signature_part(mail.body_html))
        _message, mail = self._reply(self.agent, ticket=ticket)
        self.assertIn("Courriel : desk.agent@example.com", self._signature_part(mail.body_html))

    def test_ac5_setting_on_from_team(self):
        self._enable_policy()
        self.company.sudo().mail_send_from_signature_address = True
        self.team.mail_send_as_alias_id = self.sac_alias
        message, mail = self._reply(self.agent)
        self.assertEqual(message.email_from, '"Desk Agent (Care Test)" <%s>' % self.sac_email)
        self.assertEqual(mail.email_from, message.email_from)
        self.assertEqual(email_normalize(mail.reply_to), self.sac_email)

    def test_ac6_customer_untouched(self):
        self.company.sudo().mail_send_from_signature_address = True
        message = self.ticket.message_post(
            body="My machine is down.",
            author_id=self.customer.id,
            email_from=self.customer.email_formatted,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.assertEqual(message.email_from, self.customer.email_formatted)

    def test_ac7_preview_data(self):
        self._enable_policy()
        self.team.mail_send_as_alias_id = self.sac_alias
        store = Store()
        self.ticket.with_user(self.agent)._thread_to_store(
            store, [], request_list=["mail_company_signature"]
        )
        threads = [
            t for t in store.get_result().get("mail.thread", [])
            if t.get("id") == self.ticket.id and "mailCompanySignature" in t
        ]
        self.assertEqual(len(threads), 1)
        self.assertIn("Courriel : %s" % self.sac_email, str(threads[0]["mailCompanySignature"]))
