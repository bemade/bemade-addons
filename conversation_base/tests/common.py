from odoo.addons.mail.tests.common import MailCommon, mail_new_test_user


class TriageCommon(MailCommon):
    """Shared fixtures for the triage tests: two internal users, an
    external partner with no user, and a conversation helper."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"].with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True
        )
        cls.Member = cls.env["mail.conversation.member"]
        cls.user_a = mail_new_test_user(
            cls.env,
            login="triage_a",
            name="Triage A",
            email="triage_a@example.com",
            notification_type="inbox",
            groups="base.group_user",
        )
        cls.user_b = mail_new_test_user(
            cls.env,
            login="triage_b",
            name="Triage B",
            email="triage_b@example.com",
            notification_type="inbox",
            groups="base.group_user",
        )
        cls.ext_partner = cls.env["res.partner"].create(
            {"name": "External Customer", "email": "customer@ext-example.com"}
        )

    def _conversation(self, **vals):
        vals.setdefault("name", "Triage conversation")
        return self.Conversation.create(vals)

    def _post(self, conversation, author=None, note=False, body="<p>Hello</p>"):
        """Post as ``author`` (a res.users -> posted by that user, a
        res.partner -> posted on its behalf)."""
        kwargs = {
            "body": body,
            "subtype_xmlid": "mail.mt_note" if note else "mail.mt_comment",
            "message_type": "comment",
        }
        if author is not None and author._name == "res.partner":
            kwargs["author_id"] = author.id
            return conversation.message_post(**kwargs)
        if author is not None:
            conversation = conversation.with_user(author)
        return conversation.message_post(**kwargs)

    def _member(self, conversation, user, **vals):
        row = self.Member.search(
            [("conversation_id", "=", conversation.id), ("user_id", "=", user.id)]
        )
        if row and vals:
            row.write(vals)
        elif not row:
            row = self.Member.create(
                dict(vals, conversation_id=conversation.id, user_id=user.id)
            )
        return row
