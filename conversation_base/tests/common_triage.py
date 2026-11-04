from unittest.mock import patch

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import TransactionCase


class TriageCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.internal_user = mail_new_test_user(
            cls.env, login="triage_internal", groups="base.group_user"
        )
        cls.colleague = mail_new_test_user(
            cls.env, login="triage_colleague", groups="base.group_user"
        )
        cls.team = cls.env["mail.conversation.team"].create({"name": "Triage Team"})
        cls.external = cls.env["res.partner"].create(
            {"name": "Ext Customer", "email": "ext.customer@example.com"}
        )
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Triage Transport", "sendable": True}
        )
        cls._seq = 0

    def _stub(self, author, **extra):
        type(self)._seq += 1
        stub = {
            "subject": "Q",
            "body": "<p>hi</p>",
            "author_id": author.id,
            "external_id": "ext-%s" % self._seq,
        }
        stub.update(extra)
        return stub

    def _inbound(self, target=None, **extra):
        mode = "existing" if target else "new"
        return self.Conversation._capture_stub(
            self.transport, self._stub(self.external, **extra), mode=mode, target=target
        )

    def _outbound_captured(self, target):
        return self.Conversation._capture_stub(
            self.transport,
            self._stub(self.internal_user.partner_id),
            mode="existing",
            target=target,
        )

    def _reply(self, conv):
        with patch.object(
            type(self.transport), "_send", return_value="sent-%s" % conv.id
        ):
            return conv.with_user(self.internal_user).action_reply("<p>ok</p>")

    def _set_dates(self, messages_dates):
        for message, date in messages_dates:
            message.date = date

    def _member(self, conv, user):
        return self.env["mail.conversation.member"].search(
            [("conversation_id", "=", conv.id), ("user_id", "=", user.id)]
        )

    def _note(self, conv, user=None):
        return conv.with_user(user or self.internal_user).message_post(
            body="<p>note</p>", subtype_xmlid="mail.mt_note"
        )
