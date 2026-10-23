# Acceptance criteria: "Unread" is each user's own state.
#   * Marking a conversation read (what opening it does) changes only the
#     acting user's row; the colleague keeps it unread, bold, and in the
#     Unread filter; handled/snooze/team state stay untouched.
#   * A new inbound message puts the conversation back to unread for the
#     same recipients as before, including users who had read it.
#   * A user filing a mail from their own inbox is not flagged unread by
#     that filing; every other recipient still is.
#   * Mark read / unread on a subset of rows touch only the acting user.
#   * Opening a conversation form in the real UI (list row, then the
#     form pager) leaves the opener's rows read and everyone else's alone.

from datetime import timedelta

from odoo import Command, fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged
from odoo.tools.safe_eval import safe_eval

from .common_triage import TriageCommon


class TestTriageUnreadPerUser(TriageCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team.member_ids = [Command.set([cls.internal_user.id, cls.colleague.id])]
        cls.conv = cls.Conversation.create(
            {"name": "shared", "team_id": cls.team.id}
        )
        cls.conv._triage_mark_unread_for_inbound()
        cls.snooze = fields.Datetime.now()

    def _state(self, conv, user):
        row = self._member(conv, user)
        return (row.unread, row.is_handled, row.snooze_until)

    def _unread_for(self, conv, user):
        return conv in self.Conversation.with_user(user).search(
            [("my_unread", "=", True)]
        )

    def test_read_is_per_user(self):
        a, b = self.internal_user, self.colleague
        self.assertTrue(self._unread_for(self.conv, a))
        before_b = self._state(self.conv, b)
        self.conv.with_user(a).action_triage_mark_read()
        self.assertFalse(self._member(self.conv, a).unread)
        self.assertFalse(self._unread_for(self.conv, a))
        self.assertTrue(self._unread_for(self.conv, b))
        self.assertEqual(self._state(self.conv, b), before_b)
        self.assertEqual(self.conv.state, "open")

    def test_unread_filters_follow_the_user(self):
        a, b = self.internal_user, self.colleague
        saved = self.env.ref("conversation_base.ir_filter_conversation_unread")
        self.conv.with_user(a).action_triage_mark_read()
        domain = [("id", "=", self.conv.id)] + safe_eval(
            saved.domain, {"uid": a.id}
        )
        self.assertFalse(self.Conversation.with_user(a).search(domain))
        domain_b = [("id", "=", self.conv.id)] + safe_eval(
            saved.domain, {"uid": b.id}
        )
        self.assertTrue(self.Conversation.with_user(b).search(domain_b))

    def test_inbound_flags_readers_again(self):
        a, b = self.internal_user, self.colleague
        self.conv.with_user(a).action_triage_mark_read()
        self.conv.with_user(b).action_triage_mark_read()
        self._inbound(self.conv)
        self.assertTrue(self._member(self.conv, a).unread)
        self.assertTrue(self._member(self.conv, b).unread)

    def test_filer_is_not_flagged_by_own_filing(self):
        a, b = self.internal_user, self.colleague
        self.conv.with_user(a).action_triage_mark_read()
        self.conv.with_user(b).action_triage_mark_read()
        self.Conversation.with_user(a)._capture_stub(
            self.transport,
            self._stub(self.external),
            mode="existing",
            target=self.conv.with_user(a),
        )
        self.assertFalse(self._member(self.conv, a).unread)
        self.assertTrue(self._member(self.conv, b).unread)

    def test_filer_not_flagged_on_new_conversation(self):
        a, b = self.internal_user, self.colleague
        # Filing from a team's inbox: the new conversation lands on that
        # team at creation, so A is already a recipient when the item is
        # posted. Only the filing exemption keeps A's row read.
        conv = (
            self.Conversation.with_user(a)
            .with_context(default_team_id=self.team.id)
            ._capture_stub(self.transport, self._stub(self.external), mode="new")
        )
        self.assertEqual(conv.team_id, self.team)
        self.assertTrue(self._member(conv, b).unread)
        self.assertFalse(self._member(conv, a).unread)
        # Only the filing itself is exempt: a later inbound reaches A again.
        self._inbound(conv)
        self.assertTrue(self._member(conv, a).unread)
        self.assertTrue(self._member(conv, b).unread)

    def test_filer_keeps_earlier_unread(self):
        # Filing never touches the filer's row: an earlier unread remains.
        a = self.internal_user
        self.assertTrue(self._member(self.conv, a).unread)
        self.Conversation.with_user(a)._capture_stub(
            self.transport,
            self._stub(self.external),
            mode="existing",
            target=self.conv.with_user(a),
        )
        self.assertTrue(self._member(self.conv, a).unread)

    def test_bulk_mark_touches_only_selected_rows_of_actor(self):
        a, b = self.internal_user, self.colleague
        c2 = self.Conversation.create({"name": "c2", "team_id": self.team.id})
        c3 = self.Conversation.create({"name": "c3", "team_id": self.team.id})
        (c2 | c3)._triage_mark_unread_for_inbound()
        (self.conv | c2).with_user(a).action_triage_mark_read()
        self.assertFalse(self._member(self.conv, a).unread)
        self.assertFalse(self._member(c2, a).unread)
        self.assertTrue(self._member(c3, a).unread)
        for conv in (self.conv, c2, c3):
            self.assertTrue(self._member(conv, b).unread)
        (self.conv | c2).with_user(a).action_triage_mark_unread()
        self.assertTrue(self._member(c2, a).unread)
        self.assertEqual(c2.state, "open")


@tagged("post_install", "-at_install")
class TestConversationOpenMarksRead(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="open_read_a", name="Reader A", groups="base.group_user"
        )
        cls.colleague = mail_new_test_user(
            cls.env, login="open_read_b", name="Reader B", groups="base.group_user"
        )
        team = cls.env["mail.conversation.team"].create(
            {
                "name": "Open Team",
                "member_ids": [Command.set([cls.user.id, cls.colleague.id])],
            }
        )
        customer = cls.env["res.partner"].create(
            {"name": "Open Customer", "email": "open.customer@example.com"}
        )
        cls.convs = {}
        for name, hours in (("Omega", 1), ("Psi", 2)):
            conv = (
                cls.env["mail.conversation"]
                .with_context(mail_create_nosubscribe=True, mail_create_nolog=True)
                .create({"name": "%s conversation" % name, "team_id": team.id})
            )
            conv.message_post(
                body="<p>Hello %s</p>" % name,
                date=fields.Datetime.now() - timedelta(hours=hours),
                author_id=customer.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            cls.convs[name] = conv

    def _member(self, conv, user):
        return self.env["mail.conversation.member"].search(
            [("conversation_id", "=", conv.id), ("user_id", "=", user.id)]
        )

    def test_open_marks_read_only_me(self):
        for conv in self.convs.values():
            self.assertTrue(self._member(conv, self.user).unread)
            self.assertTrue(self._member(conv, self.colleague).unread)
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_open_marks_read_tour",
            login=self.user.login,
        )
        self.env.invalidate_all()
        for conv in self.convs.values():
            self.assertFalse(self._member(conv, self.user).unread, conv.name)
            other = self._member(conv, self.colleague)
            self.assertTrue(other.unread, conv.name)
            self.assertFalse(other.is_handled)
            self.assertEqual(conv.state, "open")
