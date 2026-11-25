from odoo import Command
from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user


class TeamInboxCommon(MailCommon):
    """A team with an alias, two internal members and a mail server for the
    team's domain."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.member_a = mail_new_test_user(
            cls.env, login="ti_member_a", name="Member A", groups="base.group_user"
        )
        cls.member_b = mail_new_test_user(
            cls.env, login="ti_member_b", name="Member B", groups="base.group_user"
        )
        cls.outsider = mail_new_test_user(
            cls.env, login="ti_outsider", name="Outsider", groups="base.group_user"
        )
        cls.team_server = cls.env["ir.mail_server"].create(
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
                "member_ids": [Command.set([cls.member_a.id, cls.member_b.id])],
            }
        )
        cls.alias_email = cls.team.alias_email

    def _mime(self, msg_id, subject="Quote request", in_reply_to=None, to=None, cc=None):
        headers = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\n"
            "Subject: %s\n"
            "From: Real Customer <customer@client.example>\n"
            "To: %s\n"
        ) % (msg_id, subject, to or self.alias_email)
        if cc:
            headers += "Cc: %s\n" % cc
        if in_reply_to:
            headers += "In-Reply-To: %s\nReferences: %s\n" % (in_reply_to, in_reply_to)
        return (
            headers
            + 'Content-Type: text/plain; charset="UTF-8"\n\nHello, I need a quote.\n'
        )

    def _inbound(self, msg_id, **kwargs):
        thread_id = (
            self.env["mail.thread"]
            .sudo()
            .message_process(False, self._mime(msg_id, **kwargs))
        )
        return self.env["mail.conversation"].browse(thread_id)
