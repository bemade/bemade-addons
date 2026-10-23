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
#   * Opening a conversation by any path enrols the opener: a user who is
#     neither assignee nor on the team and had no member row gets one
#     (read), so the next inbound message flags them unread like everyone
#     who already opened it. Nobody else gets a row or a change.

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

    def test_outsider_open_enrols_then_inbound_flags(self):
        a, b = self.internal_user, self.colleague
        outsider = mail_new_test_user(
            self.env, login="triage_outsider", groups="base.group_user"
        )
        self.assertFalse(self._member(self.conv, outsider))
        before = {user: self._state(self.conv, user) for user in (a, b)}
        # What the conversation form does on load, whatever the way in.
        self.conv.with_user(outsider).action_triage_mark_read()
        self.assertEqual(self._state(self.conv, outsider), (False, False, False))
        self.assertFalse(self._unread_for(self.conv, outsider))
        for user in (a, b):
            self.assertEqual(self._state(self.conv, user), before[user])
        self.assertEqual(self.conv.member_ids.user_id, a | b | outsider)
        self.assertEqual(self.conv.state, "open")
        self._inbound(self.conv)
        for user in (outsider, a, b):
            self.assertTrue(self._member(self.conv, user).unread, user.login)
        self.assertTrue(self._unread_for(self.conv, outsider))

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
        cls.customer = customer = cls.env["res.partner"].create(
            {"name": "Open Customer", "email": "open.customer@example.com"}
        )
        # The tour searches "suivi lecture" to narrow the list to these two.
        # "Sigma" is noise: an unread, more recent conversation in the same
        # default list, as a database with other data would have. The tour
        # must not depend on what else the list holds, nor on the order.
        cls.convs = {}
        for name, hours in (("Sigma", 0), ("Omega", 1), ("Psi", 2)):
            label = "Sigma other" if name == "Sigma" else "%s suivi lecture" % name
            conv = (
                cls.env["mail.conversation"]
                .with_context(mail_create_nosubscribe=True, mail_create_nolog=True)
                .create({"name": label, "team_id": team.id})
            )
            conv.message_post(
                body="<p>Hello %s</p>" % name,
                date=fields.Datetime.now() - timedelta(hours=hours),
                author_id=customer.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            cls.convs[name] = conv
        cls.noise = cls.convs.pop("Sigma")

    def _member(self, conv, user):
        return self.env["mail.conversation.member"].search(
            [("conversation_id", "=", conv.id), ("user_id", "=", user.id)]
        )

    def test_open_marks_read_only_me(self):
        for conv in (*self.convs.values(), self.noise):
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
        # Not opened: still unread for the reader.
        self.assertTrue(self._member(self.noise, self.user).unread)

    def test_outsider_open_by_url_enrols_reader(self):
        # Neither assignee nor on the team, and no member row: opening the
        # conversation by its link must enrol them (read), so the next
        # inbound message reaches their Unread.
        outsider = mail_new_test_user(
            self.env, login="open_read_out", name="Reader Out", groups="base.group_user"
        )
        conv = self.convs["Omega"]
        others = (self.convs["Psi"], self.noise)
        self.assertFalse(self._member(conv, outsider))
        before = {
            user: (row.unread, row.is_handled, row.snooze_until)
            for user in (self.user, self.colleague)
            for row in self._member(conv, user)
        }
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action/%s" % conv.id,
            "conversation_open_enrols_reader_tour",
            login=outsider.login,
        )
        self.env.invalidate_all()
        row = self._member(conv, outsider)
        self.assertTrue(row, "opening must enrol the opener")
        self.assertFalse(row.unread)
        self.assertFalse(row.is_handled)
        for user in (self.user, self.colleague):
            row_other = self._member(conv, user)
            self.assertEqual(
                (row_other.unread, row_other.is_handled, row_other.snooze_until),
                before[user],
            )
        self.assertEqual(
            conv.member_ids.user_id, self.user | self.colleague | outsider
        )
        self.assertEqual(conv.state, "open")
        for other in others:
            self.assertFalse(self._member(other, outsider), other.name)
        # A new inbound message now reaches the outsider too.
        conv.message_post(
            body="<p>Follow-up</p>",
            author_id=self.customer.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.assertTrue(self._member(conv, outsider).unread)
