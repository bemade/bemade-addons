# Acceptance criteria:
#   * A reply draft on a conversation answered from a team mailbox (the
#     conversation came in through the team alias) has no signature prefilled.
#   * A draft on a personal or shared non-team transport still starts with the
#     acting user's signature.

from odoo import Command
from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user


class TestDraftTeamSignature(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="dts_user", name="Sig User", groups="base.group_user"
        )
        cls.user.signature = "<p>Regards, TEAMTEST-SIGNATURE</p>"
        cls.env["ir.mail_server"].create(
            {
                "name": "Team domain server",
                "smtp_host": "smtp_host",
                "smtp_encryption": "none",
                "from_filter": "team.example.com",
            }
        )
        cls.team = cls.env["mail.conversation.team"].create(
            {
                "name": "Sales Desk",
                "alias_name": "sales-desk",
                "alias_domain_id": cls.mail_alias_domain.id,
                "from_address": "sales@team.example.com",
                "member_ids": [Command.set([cls.user.id])],
            }
        )
        cls.Draft = cls.env["mail.conversation.draft"]

    def _draft_for(self, transport):
        conversation = self.env["mail.conversation"].create(
            {"name": "Question", "primary_transport_id": transport.id}
        )
        return self.Draft.browse(
            conversation.with_user(self.user).action_open_draft()["res_id"]
        )

    def test_team_mailbox_draft_has_no_signature(self):
        team_transport = self.team.team_transport_id
        self.assertEqual(team_transport.provider, "team_smtp")
        draft = self._draft_for(team_transport)
        self.assertEqual(draft.transport_id, team_transport)
        self.assertFalse(draft.body)

    def test_conversation_created_by_the_team_alias(self):
        mime = (
            "MIME-Version: 1.0\nMessage-ID: <dts-1@client.example>\n"
            "Subject: Quote\nFrom: Customer <customer@client.example>\n"
            f"To: {self.team.alias_email}\n"
            'Content-Type: text/plain; charset="UTF-8"\n\nHello.\n'
        )
        thread_id = (
            self.env["mail.thread"].sudo().message_process(False, mime)
        )
        conversation = self.env["mail.conversation"].browse(thread_id)
        draft = self.Draft.browse(
            conversation.with_user(self.user).action_open_draft()["res_id"]
        )
        self.assertEqual(draft.transport_id, self.team.team_transport_id)
        self.assertFalse(draft.body)

    def test_personal_and_shared_transports_keep_the_signature(self):
        Transport = self.env["conversation.transport"]
        for user_id in (self.user.id, False):
            transport = Transport.create(
                {"name": "Plain", "sendable": True, "user_id": user_id}
            )
            draft = self._draft_for(transport)
            self.assertEqual(draft.body.count("TEAMTEST-SIGNATURE"), 1)
            draft.action_discard()
