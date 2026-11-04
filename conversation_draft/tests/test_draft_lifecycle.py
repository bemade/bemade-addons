# Acceptance criteria (collaborative shared drafts):
#   * "Reply" opens the conversation's one active draft; calling it again
#     returns that same draft, and only a discarded/sent draft frees the slot.
#   * The database refuses a second active (draft or sending) draft.
#   * Two near-simultaneous "Reply" clicks never produce two drafts: outside a
#     request the loser gets a clear error, inside one a retryable
#     ConcurrencyError.
#   * A draft survives reassigning the conversation, with everything on it.

from unittest.mock import MagicMock, patch

import psycopg2
from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import ConcurrencyError, UserError
from odoo.tools import mute_logger

from .common import DraftCommon

DRAFT_MODULE = "odoo.addons.conversation_draft.models.mail_conversation_draft"


class TestDraftLifecycle(DraftCommon):
    def test_reply_reuses_the_active_draft(self):
        first = self._open_draft()
        second = self._open_draft(self.user_b)
        self.assertEqual(first, second)
        self.conversation.invalidate_recordset()
        self.assertEqual(self.conversation.active_draft_id, first)
        self.assertTrue(self.conversation.has_pending_draft)

        first.action_discard()
        third = self._open_draft()
        self.assertNotEqual(third, first)

        with self._sending():
            third.action_send()
        fourth = self._open_draft()
        self.assertNotIn(fourth, (first, third))
        self.conversation.invalidate_recordset()
        drafts = self.conversation.draft_ids
        self.assertEqual(
            {d.id: d.state for d in drafts},
            {first.id: "discarded", third.id: "sent", fourth.id: "draft"},
        )

    def test_search_on_pending_draft(self):
        Conversation = self.env["mail.conversation"]
        self.assertNotIn(
            self.conversation, Conversation.search([("has_pending_draft", "=", True)])
        )
        draft = self._open_draft()
        self.assertIn(
            self.conversation, Conversation.search([("has_pending_draft", "=", True)])
        )
        self.assertIn(
            self.conversation, Conversation.search([("active_draft_id", "=", draft.id)])
        )
        self.assertNotIn(
            self.conversation, Conversation.search([("active_draft_id", "=", False)])
        )

    def _create_raw(self, state="draft"):
        return self.Draft.create(
            {"conversation_id": self.conversation.id, "state": state}
        )

    def test_database_allows_one_active_draft(self):
        first = self._create_raw()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._create_raw()
        # a settled draft frees the slot
        first.state = "sent"
        self.env.flush_all()
        second = self._create_raw()
        self.assertEqual(second.state, "draft")

    def test_sending_draft_occupies_the_slot(self):
        first = self._create_raw("sending")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._create_raw("draft")
        first.state = "draft"
        self.env.flush_all()
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self._create_raw("sending")

    def _lose_the_race(self):
        self._create_raw()
        return patch.object(
            type(self.Draft), "_active_for", return_value=self.Draft.browse()
        )

    def test_concurrent_reply_outside_a_request_gets_a_clear_error(self):
        with self._lose_the_race(), mute_logger("odoo.sql_db"):
            with self.assertRaisesRegex(UserError, "colleague has just started"):
                self.Draft._get_or_create_for(self.conversation)

    def test_concurrent_reply_inside_a_request_is_retryable(self):
        with (
            self._lose_the_race(),
            patch(f"{DRAFT_MODULE}.request", MagicMock()),
            mute_logger("odoo.sql_db"),
        ):
            with self.assertRaises(ConcurrencyError):
                self.Draft._get_or_create_for(self.conversation)

    def test_draft_survives_reassignment(self):
        draft = self._open_draft(self.user_a)
        draft.write(
            {
                "body": "<p>Work in progress</p>",
                "recipient_ids": [
                    Command.create({"email": "extra@example.com", "mode": "cc"})
                ],
            }
        )
        attachment = self.env["ir.attachment"].create(
            {
                "name": "spec.txt",
                "raw": b"data",
                "res_model": draft._name,
                "res_id": draft.id,
            }
        )
        draft.write({"attachment_ids": [Command.link(attachment.id)]})
        comment = draft.message_post(body="Check the tone", subtype_xmlid="mail.mt_note")

        self.conversation.action_reassign(user=self.user_b, team=self.team)

        same = self._open_draft(self.user_b)
        self.assertEqual(same, draft)
        self.assertIn("Work in progress", same.body)
        self.assertIn("extra@example.com", same.recipient_ids.mapped("email"))
        self.assertEqual(same.attachment_ids, attachment)
        self.assertIn(comment, same.message_ids)
        same.write({"body": "<p>Edited by B</p>"})
        with self._sending() as mocked:
            same.action_send()
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(same.state, "sent")
        self.assertEqual(same.sent_by_id, self.user_b)

    def test_discarded_draft_is_read_only(self):
        draft = self._open_draft()
        draft.action_discard()
        with self.assertRaises(UserError):
            draft.write({"body": "<p>late</p>"})
        with self.assertRaises(UserError):
            draft.action_discard()
