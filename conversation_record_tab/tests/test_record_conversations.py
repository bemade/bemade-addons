# Acceptance criteria for the record-side "Relevant Conversations" payload:
# - every conversation linked to a record is listed, whatever created the
#   link (manual row, row added on the conversation form), in every state,
#   newest activity first (conversations without a message last);
# - the count matches the rows; removing a link or deleting the conversation
#   removes it; a record with no link gets an empty payload;
# - linking posts nothing on the record;
# - internal users (not only admins) get the list, portal users get nothing
#   and no access error;
# - the scopes are an extension point (list of scopes, optional "via").

from datetime import timedelta

from odoo import Command, fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import Form, TransactionCase, tagged

from ..models.mail_conversation_link import MailConversationLink


@tagged("post_install", "-at_install")
class TestRecordConversations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="rec_tab_user", groups="base.group_user"
        )
        cls.portal = mail_new_test_user(
            cls.env, login="rec_tab_portal", groups="base.group_portal"
        )
        cls.record = cls.env["res.partner"].create({"name": "Tab Record"})
        cls.other = cls.env["res.partner"].create({"name": "Tab Other Record"})
        cls.Conversation = cls.env["mail.conversation"].with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True
        )
        cls.Link = cls.env["mail.conversation.link"]

    def _conversation(self, name, hours_ago=None, **vals):
        conversation = self.Conversation.create({"name": name, **vals})
        if hours_ago is not None:
            conversation.message_post(
                body="Hello %s" % name,
                date=fields.Datetime.now() - timedelta(hours=hours_ago),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
        return conversation

    def _link(self, conversation, record=None, **vals):
        record = record or self.record
        return self.Link.create(
            {
                "conversation_id": conversation.id,
                "res_model": record._name,
                "res_id": record.id,
                **vals,
            }
        )

    def _payload(self, record=None, user=None):
        record = record or self.record
        return (
            self.Link.with_user(user or self.user)
            .get_record_conversations(record._name, record.id)
        )

    def _names(self, payload):
        return [row["name"] for s in payload["scopes"] for row in s["conversations"]]

    def test_manual_link_is_listed(self):
        conversation = self._conversation("From inbox", hours_ago=1)
        self._link(conversation, reason="manual")
        payload = self._payload()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(self._names(payload), ["From inbox"])
        self.assertEqual(payload["scopes"][0]["key"], "linked")

    def test_row_added_on_conversation_form_is_listed(self):
        conversation = self._conversation("Via form")
        with Form(conversation) as form:
            with form.link_ids.new() as line:
                line.res_model = self.record._name
                line.res_id = self.record.id
        self.assertEqual(conversation.link_ids.reason, "direct")
        self.assertEqual(self._names(self._payload()), ["Via form"])

    def test_all_states_and_per_user_triage_do_not_filter(self):
        states = ("open", "snoozed", "waiting", "done")
        for state in states:
            conversation = self._conversation("C %s" % state, state=state)
            self._link(conversation)
        hidden = self.Conversation.search([("name", "=", "C open")])
        hidden.with_user(self.user).action_triage_hide()
        self.assertTrue(hidden.with_user(self.user).my_hidden)
        payload = self._payload()
        rows = payload["scopes"][0]["conversations"]
        self.assertEqual(payload["count"], 4)
        self.assertEqual({r["state"] for r in rows}, set(states))
        done = next(r for r in rows if r["state"] == "done")
        self.assertEqual(done["state_label"], "Done")

    def test_order_count_and_assignee(self):
        old = self._conversation("Old", hours_ago=10)
        new = self._conversation("New", hours_ago=1, user_id=self.user.id)
        # No message: newest activity falls back to the creation date.
        empty = self._conversation("No message yet")
        for conversation in (old, empty, new):
            self._link(conversation)
        payload = self._payload()
        rows = payload["scopes"][0]["conversations"]
        self.assertEqual([r["name"] for r in rows], ["No message yet", "New", "Old"])
        self.assertEqual(payload["count"], len(rows))
        self.assertTrue(rows[0]["last_message_date"])
        self.assertFalse(rows[0]["user_name"])
        self.assertEqual(rows[1]["user_name"], self.user.name)

    def test_only_this_record(self):
        mine = self._conversation("Mine")
        theirs = self._conversation("Theirs")
        self._link(mine)
        self._link(theirs, record=self.other)
        self.assertEqual(self._names(self._payload()), ["Mine"])

    def test_unlink_and_delete_remove_it(self):
        keep = self._conversation("Keep", hours_ago=1)
        drop = self._conversation("Drop link", hours_ago=2)
        gone = self._conversation("Delete conv", hours_ago=3)
        self._link(keep)
        link = self._link(drop)
        self._link(gone)
        self.assertEqual(self._payload()["count"], 3)
        link.unlink()
        gone.unlink()
        self.assertEqual(self._names(self._payload()), ["Keep"])

    def test_no_link_gives_empty_payload(self):
        self.assertEqual(self._payload(), {"count": 0, "scopes": []})

    def test_conversation_linked_to_a_conversation_gets_nothing(self):
        target = self._conversation("Target conversation", hours_ago=1)
        source = self._conversation("Source conversation", hours_ago=2)
        self._link(source, record=target)
        self.assertEqual(
            self.Link._conversations_for_record("mail.conversation", target.id),
            source,
        )
        self.assertEqual(self._payload(record=target), {"count": 0, "scopes": []})

    def test_linking_posts_nothing_on_the_record(self):
        self.record.message_post(body="Existing")
        before = self.env["mail.message"].search_count(
            [("model", "=", "res.partner"), ("res_id", "=", self.record.id)]
        )
        followers = self.record.message_follower_ids
        conversation = self._conversation("Silent", hours_ago=1)
        self._link(conversation, reason="manual")
        self._payload()
        after = self.env["mail.message"].search_count(
            [("model", "=", "res.partner"), ("res_id", "=", self.record.id)]
        )
        self.assertEqual(before, after)
        self.assertEqual(self.record.message_follower_ids, followers)
        self.assertEqual(conversation.message_ids.mapped("model"), ["mail.conversation"])

    def test_portal_user_gets_nothing_without_error(self):
        self._link(self._conversation("Internal only"))
        self.assertEqual(
            self._payload(user=self.portal), {"count": 0, "scopes": []}
        )
        self.assertEqual(self._payload()["count"], 1)

    def test_scopes_are_extensible(self):
        self._link(self._conversation("Direct"))
        original = MailConversationLink._record_conversation_scopes

        def extended(self_, res_model, res_id):
            scopes = original(self_, res_model, res_id)
            row = {
                "id": 0,
                "name": "Related",
                "state": "open",
                "state_label": "Open",
                "user_name": False,
                "last_message_date": False,
                "via": "via SO-1",
            }
            return scopes + [
                {"key": "related", "label": "Related", "count": 1, "conversations": [row]}
            ]

        self.patch(MailConversationLink, "_record_conversation_scopes", extended)
        payload = self._payload()
        self.assertEqual([s["key"] for s in payload["scopes"]], ["linked", "related"])
        self.assertEqual(payload["count"], 2)
