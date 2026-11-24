# Acceptance criteria: a mail received on the team's own address together
# with two outside people lists the sender and those two people as
# participants, never the team's address. A browser tour drives the real
# conversation form; the server side proves the stored participants.

from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestConversationOwnAddressTour(HttpCase, MailCommon):
    def test_team_address_not_listed_as_participant(self):
        user = mail_new_test_user(
            self.env, login="tour_own_u", name="Tour Member", groups="base.group_user"
        )
        user.group_ids += self.env.ref("base.group_system")
        alias = self.env["mail.alias"].create(
            {
                "alias_name": "equipe-soumissions",
                "alias_model_id": self.env["ir.model"]._get("mail.conversation").id,
                "alias_domain_id": self.mail_alias_domain.id,
            }
        )
        raw = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: <tour-own-address@example.com>\n"
            "Subject: Soumission\n"
            "From: Client Tremblay <client@example.net>\n"
            "To: %s@%s, Marie Roy <marie@example.org>, jean@example.org\n"
            'Content-Type: text/plain; charset="UTF-8"\n\n'
            "Bonjour\n"
        ) % (alias.alias_name, self.mail_alias_domain.name)
        conversation_id = self.env["mail.thread"].sudo().message_process(False, raw)
        conversation = self.env["mail.conversation"].browse(conversation_id)
        self.assertEqual(
            set(conversation.participant_ids.mapped("email_normalized")),
            {"client@example.net", "marie@example.org", "jean@example.org"},
        )
        self.env.cr.flush()
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_own_address_tour",
            login=user.login,
        )
