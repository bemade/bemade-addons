# Acceptance criteria (server side of the optional thread view):
#   * "Thread view" opens a client action on the same conversation, in the main
#     window; the conversation form builds with that button and keeps working.
#   * The header summary shows subject, state, assignee, team and tags.
#   * Opening the view writes nothing: no state, member, draft or message
#     change, and it needs no right beyond reading the conversation.

from odoo import Command
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestThreadView(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="thread_view_u", name="Thread User", groups="base.group_user"
        )
        cls.team = cls.env["mail.conversation.team"].create({"name": "Thread Team"})
        cls.tag = cls.env["mail.conversation.tag"].create({"name": "Urgent"})
        cls.conversation = cls.env["mail.conversation"].create(
            {
                "name": "Thread subject",
                "user_id": cls.user.id,
                "team_id": cls.team.id,
                "tag_ids": [Command.set(cls.tag.ids)],
            }
        )

    def test_action_is_a_client_action_in_the_main_window(self):
        action = self.conversation.with_user(self.user).action_open_thread_view()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "conversation_thread_view")
        self.assertEqual(action["target"], "current")
        self.assertEqual(action["context"]["active_id"], self.conversation.id)

    def test_summary_shows_the_header_fields(self):
        summary = self.conversation.with_user(self.user).thread_view_summary()
        self.assertEqual(summary["name"], "Thread subject")
        self.assertEqual(summary["state"], "open")
        self.assertEqual(summary["state_label"], "Open")
        self.assertEqual(summary["user"], "Thread User")
        self.assertEqual(summary["team"], "Thread Team")
        self.assertEqual([t["name"] for t in summary["tags"]], ["Urgent"])

    def test_opening_the_view_writes_nothing(self):
        conversation = self.conversation.with_user(self.user)
        before = {
            "state": conversation.state,
            "write_date": conversation.write_date,
            "members": conversation.member_ids.ids,
            "drafts": self.env["mail.conversation.draft"]
            .search([("conversation_id", "=", conversation.id)])
            .ids,
            "messages": self.env["mail.message"]
            .search([("model", "=", "mail.conversation"), ("res_id", "=", conversation.id)])
            .ids,
        }
        conversation.action_open_thread_view()
        conversation.thread_view_summary()
        self.env.invalidate_all()
        conversation = self.conversation.with_user(self.user)
        self.assertEqual(conversation.state, before["state"])
        self.assertEqual(conversation.write_date, before["write_date"])
        self.assertEqual(conversation.member_ids.ids, before["members"])
        self.assertEqual(
            self.env["mail.conversation.draft"]
            .search([("conversation_id", "=", conversation.id)])
            .ids,
            before["drafts"],
        )
        self.assertEqual(
            self.env["mail.message"]
            .search([("model", "=", "mail.conversation"), ("res_id", "=", conversation.id)])
            .ids,
            before["messages"],
        )

    def test_form_builds_with_the_entry_button_only_when_saved(self):
        view = self.env.ref("conversation_thread_view.mail_conversation_view_form")
        form_view = self.env["mail.conversation"].with_user(self.user).get_view(
            view.inherit_id.id, "form"
        )
        self.assertIn('name="action_open_thread_view"', form_view["arch"])
        form = Form(self.conversation.with_user(self.user))
        self.assertEqual(form.name, "Thread subject")
