# Acceptance criteria (the reply draft prefills the user's signature):
#   * A new draft on a conversation not answered from a team mailbox has its
#     body prefilled with the acting user's signature: an empty paragraph to
#     type in, the signature, an empty paragraph.
#   * Personal, shared and empty transports all count as "no team mailbox".
#   * The signature is ordinary content: nothing is appended at send time, so
#     it is sent and recorded exactly once when kept and not at all when
#     deleted.
#   * It is prefilled once, at creation: reopening, a colleague opening the
#     shared draft and later saves never add or replace it.
#   * A user without a signature gets an empty body.
#   * A template applied to an untouched prefill goes above the signature.

from unittest.mock import patch

from .common import DraftCommon

SIGNATURE_A = "<p>Regards,<br/>Draft User A SIGNATURE-A</p>"
SIGNATURE_B = "<p>Cheers,<br/>Draft User B SIGNATURE-B</p>"


class TestDraftSignature(DraftCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a.signature = SIGNATURE_A
        cls.user_b.signature = SIGNATURE_B

    def _fresh(self, conversation=None, user=None):
        conversation = conversation or self.conversation
        self.Draft.search(
            [
                ("conversation_id", "=", conversation.id),
                ("state", "=", "draft"),
            ]
        ).action_discard()
        return self._open_draft(user=user, conversation=conversation)

    def test_prefilled_with_the_acting_users_signature(self):
        draft = self._open_draft(self.user_a)
        self.assertEqual(draft.body.count("SIGNATURE-A"), 1)
        self.assertTrue(draft.body.startswith("<p><br></p>"))
        self.assertTrue(draft.body.endswith("<p><br></p>"))
        self.assertIn("Regards,", draft.body)
        self.assertNotIn("&lt;", draft.body)

    def test_acting_user_not_creator_of_conversation(self):
        draft = self._open_draft(self.user_b)
        self.assertIn("SIGNATURE-B", draft.body)
        self.assertNotIn("SIGNATURE-A", draft.body)

    def test_personal_transport_prefills(self):
        self.t1.user_id = self.user_a
        self.assertIn("SIGNATURE-A", self._open_draft(self.user_a).body)

    def test_shared_transport_prefills(self):
        self.assertFalse(self.t1.user_id)
        self.assertIn("SIGNATURE-A", self._open_draft(self.user_a).body)

    def test_empty_transport_prefills(self):
        self.t1.user_id = self.user_b  # not readable by user A
        draft = self._open_draft(self.user_a)
        self.assertFalse(draft.transport_id)
        self.assertIn("SIGNATURE-A", draft.body)

    def test_opted_out_transport_gets_no_signature(self):
        with self._opt_out(self.t1):
            self.assertFalse(self._fresh().body)

    def _opt_out(self, transport):
        return patch.object(
            type(transport),
            "_draft_prefills_user_signature",
            autospec=True,
            side_effect=lambda rec: rec != transport,
        )

    def test_no_signature_gives_empty_body(self):
        for empty in (False, "", "<p><br></p>"):
            self.user_a.signature = empty
            draft = self._fresh(user=self.user_a)
            self.assertFalse(draft.body, f"signature {empty!r}")

    def test_reopening_and_colleague_leave_the_body_alone(self):
        draft = self._open_draft(self.user_a)
        body = draft.body
        self.assertEqual(self._open_draft(self.user_a), draft)
        colleague = self._open_draft(self.user_b)
        self.assertEqual(colleague.id, draft.id)
        self.assertEqual(colleague.body, body)
        self.assertNotIn("SIGNATURE-B", colleague.body)
        colleague.write({"subject": "Other"})
        self.assertEqual(draft.body, body)

    def test_existing_edit_survives_reopen(self):
        draft = self._open_draft(self.user_a)
        draft.write({"body": "<p>my text only</p>"})
        self.user_a.signature = SIGNATURE_B
        again = self._open_draft(self.user_a)
        self.assertEqual(again.body, "<p>my text only</p>")

    @staticmethod
    def _capture(sent):
        """A transport ``_send`` stand-in recording the body it was handed."""

        def _send(transport, conversation, message, **kwargs):
            sent.append(message.body)
            return "ext-1"

        return _send

    def test_kept_signature_is_sent_and_recorded_once(self):
        draft = self._open_draft(self.user_a)
        sent = []
        with self._sending(side_effect=self._capture(sent)):
            draft.action_send()
        self.env.invalidate_all()
        self.assertEqual(self._outbound().body.count("SIGNATURE-A"), 1)
        self.assertEqual([body.count("SIGNATURE-A") for body in sent], [1])

    def test_deleted_signature_is_not_re_added_on_send(self):
        draft = self._open_draft(self.user_a)
        draft.write({"body": "<p>No signature please</p>"})
        sent = []
        with self._sending(side_effect=self._capture(sent)):
            draft.action_send()
        self.env.invalidate_all()
        message = self._outbound()
        self.assertNotIn("SIGNATURE-A", message.body)
        self.assertIn("No signature please", message.body)
        self.assertEqual(len(sent), 1)
        self.assertNotIn("SIGNATURE-A", sent[0])

    def test_template_goes_above_an_untouched_signature(self):
        template = self.env["mail.template"].create(
            {
                "name": "Sig template",
                "model_id": self.env["ir.model"]._get_id("mail.conversation"),
                "subject": "Re: {{ object.name }}",
                "body_html": "<p>TEMPLATE-TEXT</p>",
            }
        )
        wizard = self.env["mail.conversation.draft.template"].with_user(
            self.user_a
        ).create(
            {
                "conversation_id": self.conversation.id,
                "template_id": template.id,
                "mode": "append",
            }
        )
        draft = self.Draft.browse(wizard.action_apply()["res_id"])
        self.assertEqual(draft.body.count("SIGNATURE-A"), 1)
        self.assertEqual(draft.body.count("TEMPLATE-TEXT"), 1)
        self.assertLess(
            draft.body.index("TEMPLATE-TEXT"), draft.body.index("SIGNATURE-A")
        )
