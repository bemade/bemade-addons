# Acceptance criteria (triage list):
#   * A member row is created on demand, at most one per (conversation,
#     user).
#   * An inbound message marks the assignee, the team's internal members and
#     the existing members unread; notes and answers mark nobody.
#   * An inbound message never clears a user's hidden checkmark.
#   * A per-user action touches only the acting user's own row and never the
#     conversation's state.
#   * Opening a conversation marks it read for the opening user only.

from datetime import timedelta

from odoo import Command, fields
from odoo.addons.mail.tests.common import mail_new_test_user

from .common_triage import TriageCommon


class TestTriageMembers(TriageCommon):
    def test_member_created_on_demand(self):
        conv = self.Conversation.create({"name": "c"})
        conv = conv.with_user(self.internal_user)
        conv.action_triage_hide()
        conv.action_triage_mark_unread()
        conv.action_triage_hide()
        row = self._member(conv, self.internal_user)
        self.assertEqual(len(row), 1)
        self.assertTrue(row.is_handled)
        self.assertTrue(row.unread)
        self.assertFalse(self._member(conv, self.colleague))

    def test_inbound_fans_out_unread(self):
        inactive = mail_new_test_user(
            self.env, login="triage_inactive", groups="base.group_user"
        )
        inactive.active = False
        portal = mail_new_test_user(
            self.env, login="triage_portal", groups="base.group_portal"
        )
        other = mail_new_test_user(
            self.env, login="triage_other", groups="base.group_user"
        )
        self.team.member_ids = [
            Command.set([self.colleague.id, inactive.id, portal.id])
        ]
        admin = self.env.ref("base.user_admin")
        conv = self.Conversation.create(
            {
                "name": "fan",
                "user_id": self.internal_user.id,
                "team_id": self.team.id,
                "member_ids": [
                    Command.create({"user_id": admin.id, "unread": False})
                ],
            }
        )
        self._inbound(conv)
        for user in (self.internal_user, self.colleague, admin):
            self.assertTrue(self._member(conv, user).unread, user.login)
        for user in (inactive, portal, other):
            self.assertFalse(self._member(conv, user), user.login)

    def test_note_and_answer_do_not_mark_unread(self):
        conv = self.Conversation.create(
            {
                "name": "quiet",
                "user_id": self.internal_user.id,
                "primary_transport_id": self.transport.id,
            }
        )
        conv._triage_mark_unread_for_inbound()
        members = self._member(conv, self.internal_user)
        members |= self.env["mail.conversation.member"].create(
            {"conversation_id": conv.id, "user_id": self.colleague.id}
        )
        members.write({"unread": False})
        self._note(conv)
        self._reply(conv)
        self._outbound_captured(conv)
        self.assertEqual(members.mapped("unread"), [False, False])

    def test_inbound_keeps_handled(self):
        conv = self._inbound()
        as_a = conv.with_user(self.internal_user)
        as_a.action_triage_hide()
        self._inbound(conv)
        row = self._member(conv, self.internal_user)
        self.assertTrue(row.is_handled)
        self.assertTrue(row.unread)
        Conv = self.Conversation.with_user(self.internal_user)
        self.assertNotIn(conv, Conv.search([("my_in_list", "=", True)]))
        self.assertIn(conv, Conv.search([("my_unread", "=", True)]))
        self.assertIn(conv, Conv.search([("my_hidden", "=", True)]))

    def test_per_user_isolation(self):
        conv = self.Conversation.create({"name": "iso"})
        other = self.env["mail.conversation.member"].create(
            {"conversation_id": conv.id, "user_id": self.colleague.id, "unread": True}
        )
        snapshot = other.read()
        state = conv.state
        as_a = conv.with_user(self.internal_user)
        future = fields.Datetime.now() + timedelta(hours=1)
        steps = (
            as_a.action_triage_hide,
            lambda: as_a.action_triage_snooze(future),
            as_a.action_triage_unsnooze,
            as_a.action_triage_mark_read,
            as_a.action_triage_mark_unread,
            as_a.action_triage_unhide,
        )
        for step in steps:
            step()
            self.assertEqual(other.read(), snapshot)
            self.assertEqual(conv.state, state)
        in_list = self.Conversation.with_user(self.colleague).search(
            [("my_in_list", "=", True), ("id", "=", conv.id)]
        )
        self.assertEqual(in_list, conv)

    def test_open_marks_read_only_me(self):
        conv = self.Conversation.create({"name": "open"})
        Member = self.env["mail.conversation.member"]
        mine = Member.create(
            {"conversation_id": conv.id, "user_id": self.internal_user.id, "unread": True}
        )
        theirs = Member.create(
            {"conversation_id": conv.id, "user_id": self.colleague.id, "unread": True}
        )
        conv.with_user(self.internal_user).action_triage_mark_read()
        self.assertFalse(mine.unread)
        self.assertTrue(theirs.unread)
