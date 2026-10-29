# Acceptance criteria (reply pop-up, server side):
#   * Reply (top-level or on one message) hands the client the draft in a
#     dialog over the conversation; the draft is created when missing.
#   * A reply to one message records it on the draft and quotes it under the
#     text already typed; with a draft already started, that same draft is
#     reused, never a second one.
#   * Only messages a correspondent has seen can be answered: not internal
#     notes, tracking, or another conversation's messages.
#   * Sending a reply to one message posts it as an answer to that message and
#     hands the transport the message to thread under; a top-level reply is
#     unchanged. In the pop-up, a send closes the dialog; the full form still
#     reloads.
#   * Any internal user can edit the draft in the dialog and from the Drafts
#     page; a sent draft stays read-only.

from markupsafe import Markup

from odoo.exceptions import UserError
from odoo.tests import Form

from .common import DraftCommon

DIALOG_VIEW = "conversation_draft.mail_conversation_draft_view_form_dialog"


class TestReplyPopup(DraftCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        post = cls.conversation.message_post
        cls.inbound = post(
            body=Markup("<p>When does the order ship?</p>"),
            subject="Order status",
            subtype_xmlid="mail.mt_note",
            email_from="Customer <cust@example.com>",
        )
        cls.inbound.write(
            {
                "external_id": "42",
                "message_id": "<inbound-1@client.example>",
                "incoming_email_to": "support@example.com",
            }
        )
        cls.note = post(
            body=Markup("<p>Internal chatter</p>"), subtype_xmlid="mail.mt_note"
        )
        cls.outbound = post(
            body=Markup("<p>It ships Friday.</p>"), subtype_xmlid="mail.mt_comment"
        )
        cls.outbound.write({"transport_id": cls.t1.id})

    # ------------------------------------------------------------
    # Opening
    # ------------------------------------------------------------

    def test_reply_opens_the_draft_in_a_dialog(self):
        action = self.conversation.with_user(self.user_a).action_open_draft()
        draft = self.Draft.browse(action["res_id"])
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["res_model"], "mail.conversation.draft")
        self.assertTrue(action["context"]["conversation_draft_dialog"])
        self.assertEqual(
            action["views"], [(self.env.ref(DIALOG_VIEW).id, "form")]
        )
        self.assertEqual(draft.conversation_id, self.conversation)
        self.assertEqual(draft.state, "draft")

    def test_top_level_reply_has_no_target_and_no_quote(self):
        draft = self._open_draft()
        self.assertFalse(draft.reply_to_message_id)
        self.assertFalse(draft.reply_to_label)
        self.assertNotIn("blockquote", draft.body or "")

    def test_dialog_view_smoke(self):
        draft = self._open_draft()
        with Form(draft, view=DIALOG_VIEW) as form:
            form.subject = "Via the pop-up"
            form.body = "<p>typed</p>"
        self.assertEqual(draft.subject, "Via the pop-up")

    # ------------------------------------------------------------
    # Answering one message
    # ------------------------------------------------------------

    def test_reply_to_a_message_quotes_and_records_it(self):
        action = self.conversation.with_user(self.user_a).action_open_draft(
            message_id=self.inbound.id
        )
        draft = self.Draft.browse(action["res_id"])
        self.assertEqual(draft.reply_to_message_id, self.inbound)
        for expected in (
            "<blockquote",
            "When does the order ship?",
            "Order status",
            "cust@example.com",
            "support@example.com",
        ):
            self.assertIn(expected, draft.body)
        self.assertIn("Customer", draft.reply_to_label)

    def test_reply_to_a_message_on_a_started_draft_keeps_the_text(self):
        draft = self._open_draft(self.user_b)
        draft.write({"body": "<p>Colleague already wrote this.</p>"})
        action = self.conversation.with_user(self.user_a).action_open_draft(
            message_id=self.inbound.id
        )
        self.assertEqual(action["res_id"], draft.id)
        self.assertEqual(self.Draft.search_count(
            [("conversation_id", "=", self.conversation.id),
             ("state", "=", "draft")]
        ), 1)
        draft.invalidate_recordset()
        self.assertTrue(draft.body.startswith("<p>Colleague already wrote this.</p>"))
        self.assertLess(
            draft.body.index("Colleague already wrote"),
            draft.body.index("When does the order ship?"),
        )
        self.assertEqual(draft.reply_to_message_id, self.inbound)

    def test_another_target_retargets_and_the_same_one_quotes_once(self):
        conversation = self.conversation.with_user(self.user_a)
        conversation.action_open_draft(message_id=self.inbound.id)
        action = conversation.action_open_draft(message_id=self.inbound.id)
        draft = self.Draft.browse(action["res_id"])
        self.assertEqual(draft.body.count("When does the order ship?"), 1)
        conversation.action_open_draft(message_id=self.outbound.id)
        draft.invalidate_recordset()
        self.assertEqual(draft.reply_to_message_id, self.outbound)
        self.assertIn("It ships Friday.", draft.body)
        self.assertIn("When does the order ship?", draft.body)

    def test_only_messages_a_correspondent_saw_can_be_answered(self):
        other = self.env["mail.conversation"].create({"name": "Elsewhere"})
        stranger = other.message_post(body="<p>x</p>")
        stranger.write({"external_id": "7", "message_id": "<s@x.example>"})
        found = self.conversation.reply_target_message_ids(
            [self.inbound.id, self.note.id, self.outbound.id, stranger.id]
        )
        self.assertCountEqual(found, [self.inbound.id, self.outbound.id])
        for message in (self.note, stranger):
            with self.assertRaisesRegex(UserError, "cannot be answered"):
                self.conversation.with_user(self.user_a).action_open_draft(
                    message_id=message.id
                )

    def test_replying_creates_no_partner_and_no_follower(self):
        partners = self.env["res.partner"].search_count([])
        followers = self.env["mail.followers"].search_count([])
        self._open_draft().conversation_id.with_user(self.user_a).action_open_draft(
            message_id=self.inbound.id
        )
        self.assertEqual(self.env["res.partner"].search_count([]), partners)
        self.assertEqual(self.env["mail.followers"].search_count([]), followers)

    # ------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------

    def _send_capturing(self, draft, **context):
        seen = {}

        def capture(transport, conversation, message, **kwargs):
            seen["reply_to"] = transport.env.context.get(
                "conversation_reply_to_message_id"
            )
            seen["recipients"] = kwargs.get("recipients")
            return "ext-1"

        with self._sending(side_effect=capture, return_value=None):
            result = draft.with_context(**context).action_send()
        return result, seen

    def test_send_answers_the_chosen_message(self):
        action = self.conversation.with_user(self.user_a).action_open_draft(
            message_id=self.inbound.id
        )
        draft = self.Draft.browse(action["res_id"]).with_user(self.user_a)
        _result, seen = self._send_capturing(draft)
        self.assertEqual(seen["reply_to"], self.inbound.id)
        self.env.invalidate_all()
        self.assertEqual(draft.sent_message_id.parent_id, self.inbound)
        self.assertEqual(draft.state, "sent")

    def test_top_level_send_threads_as_before(self):
        draft = self._open_draft()
        _result, seen = self._send_capturing(draft)
        self.assertFalse(seen["reply_to"])

    def test_send_in_the_dialog_closes_it(self):
        draft = self._open_draft()
        result, _seen = self._send_capturing(draft, conversation_draft_dialog=True)
        self.assertEqual(result, {"type": "ir.actions.act_window_close"})

    def test_send_in_the_full_form_still_reloads(self):
        draft = self._open_draft()
        result, _seen = self._send_capturing(draft)
        self.assertEqual(result, {"type": "ir.actions.client", "tag": "reload"})

    def test_failed_send_keeps_the_draft_target_and_text(self):
        action = self.conversation.with_user(self.user_a).action_open_draft(
            message_id=self.inbound.id
        )
        draft = self.Draft.browse(action["res_id"]).with_user(self.user_a)
        draft.write({"body": "<p>My careful answer</p>"})
        with self._sending(side_effect=RuntimeError("smtp down"), return_value=None):
            with self.assertRaisesRegex(UserError, "Sending failed"):
                draft.action_send()
        self.env.invalidate_all()
        self.assertEqual(draft.state, "draft")
        self.assertEqual(draft.reply_to_message_id, self.inbound)
        self.assertIn("My careful answer", draft.body)

    # ------------------------------------------------------------
    # Editable by anyone who can edit the draft
    # ------------------------------------------------------------

    def test_a_colleague_edits_the_draft_in_the_dialog(self):
        draft = self._open_draft(self.user_a)
        draft.write({"body": "<p>From A</p>"})
        dialog = draft.with_user(self.user_b).action_open_dialog()
        self.assertEqual(dialog["target"], "new")
        draft_b = self.Draft.browse(dialog["res_id"]).with_user(self.user_b)
        with Form(draft_b, view=DIALOG_VIEW) as form:
            form.subject = "Edited by B"
            form.transport_id = self.t2
        self.assertEqual(draft_b.subject, "Edited by B")
        self.assertEqual(draft_b.editor_id, self.user_b)
        self.assertIn("From A", draft_b.body)

    def test_a_sent_draft_opens_read_only(self):
        draft = self._open_draft()
        with self._sending():
            draft.action_send()
        dialog = draft.with_user(self.user_b).action_open_dialog()
        self.assertEqual(dialog["res_id"], draft.id)
        with self.assertRaises(UserError):
            draft.with_user(self.user_b).write({"subject": "too late"})
