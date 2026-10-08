from odoo.addons.mail.tests.common import MailCommon


class ConversationNotifyCommon(MailCommon):
    """Shared fixtures: an internal email user (the 'ghost' stock Odoo
    would email), an external partner follower, a sendable transport and a
    conversation alias."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.assignee = cls.env["res.users"].create(
            {
                "name": "Assignee Email User",
                "login": "conv_assignee",
                "email": "assignee@example.com",
                "notification_type": "email",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.other_internal = cls.env["res.users"].create(
            {
                "name": "Other Internal",
                "login": "conv_other_internal",
                "email": "other.internal@example.com",
                "notification_type": "email",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.external = cls.env["res.partner"].create(
            {"name": "Ghost External", "email": "ghost.external@example.com"}
        )
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Notify Transport", "sendable": True}
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {
                "name": "Notify Conversation",
                "primary_transport_id": cls.transport.id,
            }
        )
        conversation_model = cls.env["ir.model"]._get("mail.conversation")
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "conv-notify-test",
                "alias_model_id": conversation_model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)

    # -- helpers --------------------------------------------------

    def _follow_all(self, conversation, partners):
        conversation.message_subscribe(
            partner_ids=partners.ids,
            subtype_ids=self.env["mail.message.subtype"]
            .search(
                [
                    "|",
                    ("res_model", "=", False),
                    ("res_model", "=", "mail.conversation"),
                ]
            )
            .ids,
        )

    def _mails_to(self, email):
        """mail.mail records addressed to ``email`` (as recipient partner,
        email_to or cc)."""
        Mail = self.env["mail.mail"].sudo()
        return Mail.search(
            [
                "|",
                "|",
                ("recipient_ids.email", "=ilike", email),
                ("email_to", "ilike", email),
                ("email_cc", "ilike", email),
            ]
        )

    def _all_mails(self):
        return self.env["mail.mail"].sudo().search([])

    def _notifs(self, message, partner=None):
        domain = [("mail_message_id", "=", message.id)]
        if partner:
            domain.append(("res_partner_id", "=", partner.id))
        return self.env["mail.notification"].sudo().search(domain)

    def _inbound(self, msg_id, in_reply_to=None, from_="Ghost Sender <ghost.sender@example.com>", to=None, cc=None, route_model=False):
        headers = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\n"
            "Subject: Notify test\n"
            "From: %s\n"
            "To: %s\n"
        ) % (msg_id, from_, to or self.alias_email)
        if cc:
            headers += "Cc: %s\n" % cc
        if in_reply_to:
            headers += "In-Reply-To: %s\nReferences: %s\n" % (in_reply_to, in_reply_to)
        mime = (
            headers
            + 'Content-Type: text/plain; charset="UTF-8"\n'
            + "\n"
            + "Hello, a question.\n"
        )
        return self.env["mail.thread"].sudo().message_process(route_model, mime)
