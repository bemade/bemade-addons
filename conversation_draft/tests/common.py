from contextlib import contextmanager
from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase


class DraftCommon(TransactionCase):
    """Fixtures shared by the draft tests.

    Two internal users A and B, two sendable shared transports, and a
    conversation whose primary transport is T1 with a mix of participants:
    a bare-email requester, a ``to`` partner, a bare-email ``cc``, an
    internal colleague and an external participant with no address.
    """

    @classmethod
    def _make_user(cls, login):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": f"{login}@example.com",
                "notification_type": "inbox",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a = cls._make_user("draft_user_a")
        cls.user_b = cls._make_user("draft_user_b")
        cls.team = cls.env["mail.conversation.team"].create({"name": "Draft Team"})
        Transport = cls.env["conversation.transport"]
        cls.t1 = Transport.create({"name": "T1", "sendable": True})
        cls.t2 = Transport.create({"name": "T2", "sendable": True})
        cls.partner_p = cls.env["res.partner"].create(
            {"name": "Customer P", "email": "p@example.com"}
        )
        cls.partner_noemail = cls.env["res.partner"].create({"name": "No Address"})
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Shared draft topic", "primary_transport_id": cls.t1.id}
        )
        Participant = cls.env["mail.conversation.participant"]
        Participant.create(
            {
                "conversation_id": cls.conversation.id,
                "email": "cust@example.com",
                "role": "requester",
            }
        )
        Participant.create(
            {
                "conversation_id": cls.conversation.id,
                "partner_id": cls.partner_p.id,
                "email": cls.partner_p.email,
                "role": "to",
            }
        )
        Participant.create(
            {
                "conversation_id": cls.conversation.id,
                "email": "cc@example.com",
                "role": "cc",
            }
        )
        Participant.create(
            {
                "conversation_id": cls.conversation.id,
                "email": "internal@example.com",
                "role": "to",
                "kind": "internal",
            }
        )
        Participant.create(
            {
                "conversation_id": cls.conversation.id,
                "partner_id": cls.partner_noemail.id,
                "role": "to",
            }
        )
        cls.Draft = cls.env["mail.conversation.draft"]

    # ------------------------------------------------------------

    def _open_draft(self, user=None, conversation=None):
        conversation = (conversation or self.conversation).with_user(
            user or self.user_a
        )
        action = conversation.action_open_draft()
        return self.Draft.browse(action["res_id"]).with_user(user or self.user_a)

    def _patch_send(self, **kwargs):
        kwargs.setdefault("return_value", "ext-1")
        return patch.object(type(self.t1), "_send", autospec=True, **kwargs)

    @contextmanager
    def _sending(self, **kwargs):
        """Registry test mode (the dedicated cursors reuse the test
        transaction) plus a patched transport send; yields the mock."""
        with self.enter_registry_test_mode(), self._patch_send(**kwargs) as mocked:
            yield mocked

    def _outbound(self, conversation=None):
        return (conversation or self.conversation).message_ids.filtered(
            "transport_id"
        )

    def _set_sql_state(self, draft, state, minutes_ago=0, user=None):
        self.env.cr.execute(
            "UPDATE mail_conversation_draft SET state=%s, sent_by_id=%s, "
            "sent_date=(now() at time zone 'utc') - make_interval(mins => %s) "
            "WHERE id=%s",
            [state, (user or self.user_b).id, minutes_ago, draft.id],
        )
        self.env.invalidate_all()
