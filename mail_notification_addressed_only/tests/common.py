from odoo.addons.mail.tests.common import MailCommon


class AddressedOnlyCommon(MailCommon):
    """Shared helpers: an internal email user, an external follower and
    mail/notification lookups."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The mechanism is inert during tests unless opted in (see
        # mail.thread._addressed_only_applies).
        cls.env = cls.env(
            context=dict(cls.env.context, test_mail_notification_addressed_only=True)
        )
        group_user = cls.env.ref("base.group_user")
        cls.internal_follower = cls.env["res.users"].create(
            {
                "name": "Addressed Follower",
                "login": "addr_follower",
                "email": "addr.follower@example.com",
                "notification_type": "email",
                "group_ids": [(6, 0, [group_user.id])],
            }
        )
        cls.internal_other = cls.env["res.users"].create(
            {
                "name": "Addressed Other",
                "login": "addr_other",
                "email": "addr.other@example.com",
                "notification_type": "email",
                "group_ids": [(6, 0, [group_user.id])],
            }
        )
        cls.internal_inbox = cls.env["res.users"].create(
            {
                "name": "Addressed Inbox",
                "login": "addr_inbox",
                "email": "addr.inbox@example.com",
                "notification_type": "inbox",
                "group_ids": [(6, 0, [group_user.id])],
            }
        )
        cls.external = cls.env["res.partner"].create(
            {"name": "Addressed External", "email": "addr.external@example.com"}
        )

    @classmethod
    def _list_model(cls, model_name):
        Rule = cls.env["mail.addressed.only.rule"].with_context(active_test=False)
        model = cls.env["ir.model"]._get(model_name)
        rule = Rule.search([("model_id", "=", model.id)])
        if rule:
            rule.active = True
        else:
            Rule.create({"model_id": model.id})

    @classmethod
    def _follow(cls, record, partners):
        record.message_subscribe(
            partner_ids=partners.ids,
            subtype_ids=[cls.env.ref("mail.mt_comment").id],
        )

    def _post(self, record, author=None, **kwargs):
        kwargs.setdefault("body", "hello")
        kwargs.setdefault("subtype_xmlid", "mail.mt_comment")
        kwargs.setdefault("message_type", "comment")
        with self.mock_mail_gateway():
            if author:
                record = record.with_user(author)
            message = record.message_post(**kwargs)
            self.env.flush_all()
        return message

    def _mails_to(self, partner):
        return self.env["mail.mail"].search(
            [("recipient_ids", "in", partner.ids)]
        ) | self.env["mail.mail"].search([("email_to", "ilike", partner.email)])

    def _inbox_notif(self, message, partner):
        return self.env["mail.notification"].search(
            [
                ("mail_message_id", "=", message.id),
                ("res_partner_id", "=", partner.id),
                ("notification_type", "=", "inbox"),
            ]
        )
