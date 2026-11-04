# Acceptance criteria (collaborative shared drafts, sending):
#   * Sending posts one outbound message over the draft's transport and sends
#     exactly once; afterwards the draft is read-only.
#   * A replayed/retried request, or a concurrent second click, never sends
#     again: the committed claim turns it into "already sent".
#   * A transport failure keeps the draft editable and leaves nothing behind
#     on the conversation (no message, no attachment copy, no participant).
#   * To/Cc/Bcc reach the transport as three lists; a recipient without an
#     address is dropped from all of them; Bcc is never filed anywhere.

from unittest.mock import patch

import psycopg2.errors

from odoo import Command
from odoo.exceptions import UserError

from .common import DraftCommon


class TestDraftSend(DraftCommon):
    def _explicit_draft(self):
        draft = self._open_draft()
        draft.recipient_ids.unlink()
        draft.write(
            {
                "body": "<p>The answer</p>",
                "recipient_ids": [
                    Command.create({"email": "cust@example.com", "mode": "to"}),
                    Command.create({"email": "cc@example.com", "mode": "cc"}),
                    Command.create({"email": "hidden@example.com", "mode": "bcc"}),
                    Command.create(
                        {"partner_id": self.partner_noemail.id, "mode": "cc"}
                    ),
                ],
            }
        )
        return draft

    def test_single_send_then_read_only(self):
        draft = self._open_draft()
        with self._sending() as mocked:
            draft.action_send()
            self.assertEqual(mocked.call_count, 1)
            with self.assertRaisesRegex(UserError, "already sent"):
                draft.action_send()
            self.assertEqual(mocked.call_count, 1)
        self.env.invalidate_all()
        outbound = self._outbound()
        self.assertEqual(len(outbound), 1)
        self.assertEqual(outbound.transport_id, self.t1)
        self.assertEqual(outbound.external_id, "ext-1")
        self.assertEqual(draft.state, "sent")
        self.assertEqual(draft.sent_message_id, outbound)
        self.assertEqual(draft.sent_by_id, self.user_a)
        self.assertTrue(draft.sent_date)
        with self.assertRaises(UserError):
            draft.write({"body": "<p>too late</p>"})
        with self.assertRaises(UserError):
            self.env["mail.conversation.draft.recipient"].create(
                {"draft_id": draft.id, "email": "late@example.com"}
            )

    def test_replayed_request_never_resends(self):
        draft = self._open_draft()

        def during_send(transport, conversation, message, **kwargs):
            self.env.cr.execute(
                "SELECT state FROM mail_conversation_draft WHERE id = %s", [draft.id]
            )
            self.assertEqual(self.env.cr.fetchone()[0], "sending")
            with self.assertRaisesRegex(UserError, r"already sent \(or is being sent\)"):
                draft.action_send()
            return "ext-1"

        with self._sending(side_effect=during_send, return_value=None) as mocked:
            draft.action_send()
        self.assertEqual(mocked.call_count, 1)
        self.env.invalidate_all()
        self.assertEqual(draft.state, "sent")

    def test_replay_after_commit_hits_already_sent(self):
        draft = self._open_draft()
        with self._sending() as mocked:
            with patch.object(
                type(draft),
                "_after_send_action",
                side_effect=psycopg2.errors.SerializationFailure("replay me"),
            ):
                # not assertRaises: Odoo's wraps it in a savepoint that would
                # roll back the very commit this test relies on.
                raised = None
                try:
                    draft.action_send()
                except psycopg2.errors.SerializationFailure as exc:
                    raised = exc
                self.assertIsNotNone(raised, "the replayed failure should propagate")
            with self.assertRaisesRegex(UserError, "already sent"):
                draft.action_send()
            self.assertEqual(mocked.call_count, 1)

    def test_transport_failure_keeps_the_draft_and_posts_nothing(self):
        draft = self._open_draft()
        draft.write(
            {
                "recipient_ids": [
                    Command.create({"email": "brandnew@example.com", "mode": "to"})
                ],
            }
        )
        attachment = self.env["ir.attachment"].create(
            {"name": "a.txt", "raw": b"a", "res_model": draft._name, "res_id": draft.id}
        )
        draft.write({"attachment_ids": [Command.link(attachment.id)]})
        before = (
            len(self.conversation.message_ids),
            self.env["ir.attachment"].search_count([]),
            len(self.conversation.participant_ids),
        )
        seen = {}

        def failing_send(transport, conversation, message, **kwargs):
            # a colleague clicks "Reply" while the send is on the wire
            seen["draft"] = self.conversation.with_user(self.user_b).action_open_draft()
            raise Exception("smtp down")

        with self._sending(side_effect=failing_send, return_value=None):
            with self.assertRaisesRegex(UserError, "Sending failed: smtp down"):
                draft.action_send()
        self.assertEqual(seen["draft"]["res_id"], draft.id)
        self.env.invalidate_all()
        self.assertEqual(draft.state, "draft")
        self.assertFalse(draft.sent_by_id)
        self.assertFalse(draft.sent_message_id)
        self.assertEqual(
            before,
            (
                len(self.conversation.message_ids),
                self.env["ir.attachment"].search_count([]),
                len(self.conversation.participant_ids),
            ),
        )
        self.assertEqual(self.Draft.search_count([("conversation_id", "=", self.conversation.id)]), 1)
        self.assertEqual(self._open_draft(self.user_b), draft)
        draft.write({"body": "<p>still editable</p>"})

    def test_losing_a_concurrent_claim_names_the_winner(self):
        draft = self._open_draft()
        self._set_sql_state(draft, "sending", user=self.user_b)
        with self._sending() as mocked:
            with self.assertRaisesRegex(UserError, self.user_b.name):
                draft.action_send()
        mocked.assert_not_called()
        again = self._open_draft()
        self.assertEqual(again, draft)
        self.conversation.invalidate_recordset()
        self.assertEqual(self.conversation.active_draft_id, draft)
        self.assertEqual(self.Draft.search_count([("conversation_id", "=", self.conversation.id)]), 1)

    def test_stuck_send_recovery(self):
        draft = self._open_draft()
        self._set_sql_state(draft, "sending", minutes_ago=2)
        with self.assertRaisesRegex(UserError, "still being sent"):
            draft.action_return_to_draft()
        self._set_sql_state(draft, "sending", minutes_ago=11)
        self.assertTrue(draft.is_send_stuck)
        draft.action_return_to_draft()
        self.assertEqual(draft.state, "draft")
        self.assertEqual(self.Draft.search_count([("conversation_id", "=", self.conversation.id)]), 1)

        self._set_sql_state(draft, "sending", minutes_ago=11)
        draft.action_mark_sent()
        self.assertEqual(draft.state, "sent")
        self.assertFalse(draft.sent_message_id)
        self.assertNotEqual(self._open_draft(), draft)

    def test_to_cc_bcc_unreachable_and_attachments(self):
        draft = self._explicit_draft()
        attachment = self.env["ir.attachment"].create(
            {"name": "a.txt", "raw": b"a", "res_model": draft._name, "res_id": draft.id}
        )
        draft.write({"attachment_ids": [Command.link(attachment.id)]})
        partners_before = self.env["res.partner"].search_count([])
        self.assertTrue(draft.has_unreachable_recipients)
        with self._sending() as mocked:
            draft.action_send()
        kwargs = mocked.call_args.kwargs
        self.assertEqual(kwargs["recipients"], ["cust@example.com"])
        self.assertEqual(kwargs["cc"], ["cc@example.com"])
        self.assertEqual(kwargs["bcc"], ["hidden@example.com"])
        self.env.invalidate_all()
        message = draft.sent_message_id
        self.assertEqual(len(message.attachment_ids), 1)
        self.assertEqual(message.attachment_ids.res_model, "mail.conversation")
        self.assertEqual(draft.attachment_ids, attachment)
        self.assertEqual(attachment.res_model, draft._name)
        self.assertNotIn(
            "hidden@example.com",
            self.conversation.participant_ids.mapped("email_normalized"),
        )
        self.assertNotIn("hidden@example.com", message.partner_ids.mapped("email"))
        self.assertNotIn("hidden@example.com", message.body)
        self.assertEqual(partners_before, self.env["res.partner"].search_count([]))

    def test_send_needs_a_to_recipient_and_a_usable_transport(self):
        draft = self._open_draft()
        draft.recipient_ids.unlink()
        with self._sending():
            with self.assertRaisesRegex(UserError, "To recipient"):
                draft.action_send()
        draft.write(
            {"recipient_ids": [Command.create({"email": "x@example.com", "mode": "to"})]}
        )
        draft.transport_id = False
        with self._sending():
            with self.assertRaisesRegex(UserError, "transport"):
                draft.action_send()
        # nothing was claimed by the failed validations
        self.assertEqual(draft.state, "draft")

    def test_cannot_send_from_a_colleagues_personal_transport(self):
        draft = self._open_draft()
        self.t2.user_id = self.user_a
        draft.transport_id = self.t2
        self.conversation.action_reassign(user=self.user_b)
        with self._sending():
            with self.assertRaisesRegex(UserError, "transport you can send from"):
                draft.with_user(self.user_b).action_send()
