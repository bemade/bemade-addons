# Acceptance criteria (conversation_sent_recipients):
#   1. A message sent from a conversation records the To and Cc addresses
#      that were put in the mail headers, and exposes them to the web client.
#   2. What is recorded is what went out: the default To computed by the
#      transport is recorded when the caller passed none.
#   3. Bcc still receives the mail but is stored and exposed nowhere.
#   4. Inbound mail, internal notes and forward notes record nothing.
#   5. The list is fixed at send time and a failed send leaves nothing.
#   6. Recording sends no extra mail and creates no partner or follower, and
#      does not change the suggested recipients of the conversation.
#   7. Other models serialize exactly as before.

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import SentRecipientsCommon

BCC = "hidden@example.com"


@tagged("post_install", "-at_install")
class TestSentRecipients(SentRecipientsCommon):
    def _reply(self, **kwargs):
        kwargs.setdefault("recipients", ["to@example.com"])
        return self.conversation.action_reply("<p>Hello</p>", **kwargs)

    def test_to_and_cc_recorded_and_bcc_never(self):
        mails_before = self.env["mail.mail"].search_count([])
        followers_before = self.conversation.message_follower_ids
        partners_before = self.env["res.partner"].search_count([])
        message = self._reply(cc=["cc@example.com"], bcc=[BCC])

        self.assertEqual(
            sorted(self._recorded(message)),
            [("cc", "cc@example.com"), ("to", "to@example.com")],
        )
        # the recorded lists are the headers that went on the wire
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0]["To"], "to@example.com")
        self.assertEqual(self.sent[0]["Cc"], "cc@example.com")
        # Bcc was delivered through the envelope only
        self.assertIn(BCC, self.envelopes[0])
        # ... and is stored and exposed nowhere
        self.assertNotIn(BCC, str(self.sent[0]))
        self.assertFalse(
            self.env["mail.conversation.sent.recipient"].search(
                [("email", "ilike", "hidden")]
            )
        )
        message.invalidate_recordset()
        values = {name: str(message[name]) for name in message._fields if message[name]}
        self.assertFalse([n for n, v in values.items() if BCC in v], values)
        self.assertNotIn(BCC, str(self._store_payload(message)))
        # no side effects
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
        self.assertEqual(self.conversation.message_follower_ids, followers_before)
        self.assertEqual(self.env["res.partner"].search_count([]), partners_before)

    def test_store_payload_carries_to_and_cc(self):
        message = self._reply(cc=["cc@example.com"])
        payload = self._store_payload(message)["mail.message"][0]
        self.assertEqual(
            sorted((r["mode"], r["email"]) for r in payload["sent_recipients"]),
            [("cc", "cc@example.com"), ("to", "to@example.com")],
        )

    def test_default_to_computed_by_transport_is_recorded(self):
        message = self.conversation.action_reply("<p>Hello</p>")
        self.assertEqual(self.sent[0]["To"], "customer@example.com")
        self.assertEqual(self._recorded(message), [("to", "customer@example.com")])
        recipient = self.env["mail.conversation.sent.recipient"].search(
            [("message_id", "=", message.id)]
        )
        self.assertEqual(recipient.name, "Customer Person")

    def test_duplicates_are_listed_once(self):
        message = self._reply(
            recipients=["To@Example.com", "to@example.com"], cc=["to@example.com"]
        )
        self.assertEqual(
            sorted(self._recorded(message)),
            [("cc", "to@example.com"), ("to", "to@example.com")],
        )

    def test_filed_inbox_reply_records_to_and_cc_only(self):
        message_id = self.transport._send_raw(
            subject="Re: question",
            body="<p>Hi</p>",
            to_emails=["to@example.com"],
            cc=["cc@example.com"],
            bcc=[BCC],
        )
        message = self.conversation._record_outbound(
            self.transport,
            "Re: question",
            "<p>Hi</p>",
            message_id,
            to_emails=["to@example.com"],
            cc_emails=["cc@example.com"],
        )
        self.assertEqual(
            sorted(self._recorded(message)),
            [("cc", "cc@example.com"), ("to", "to@example.com")],
        )
        self.assertIn(BCC, self.envelopes[0])
        self.assertNotIn(BCC, str(self._store_payload(message)))

    def test_unfiled_send_records_nothing(self):
        self.transport._send_raw(
            subject="Re: question",
            body="<p>Hi</p>",
            to_emails=["to@example.com"],
            cc=["cc@example.com"],
        )
        self.assertFalse(self.env["mail.conversation.sent.recipient"].search([]))

    def test_inbound_note_and_forward_note_record_nothing(self):
        inbound = self.conversation.message_post(
            body="<p>Question</p>", subtype_xmlid="mail.mt_comment"
        )
        note = self.conversation.message_post(
            body="<p>Internal</p>", subtype_xmlid="mail.mt_note"
        )
        forward = self.conversation.action_forward("<p>FYI</p>", ["fwd@example.com"])
        self.assertEqual(len(self.sent), 1)
        for message in (inbound, note, forward):
            self.assertEqual(self._recorded(message), [], message.subtype_id.name)
            payload = self._store_payload(message)["mail.message"][0]
            self.assertEqual(payload["sent_recipients"], [])

    def test_recorded_list_is_fixed_at_send_time(self):
        message = self._reply(cc=["cc@example.com"])
        before = sorted(self._recorded(message))
        self.partner.email = "changed@example.com"
        self.conversation.participant_ids.unlink()
        self.assertEqual(sorted(self._recorded(message)), before)
        self.env["mail.conversation.sent.recipient"]._record_for_message(
            message, ["other@example.com"], []
        )
        self.assertEqual(sorted(self._recorded(message)), before)

    def test_failed_send_leaves_nothing(self):
        transport_cls = type(self.transport)
        orig = transport_cls._record_sent_recipients

        def record_then_fail(transport, *args, **kwargs):
            orig(transport, *args, **kwargs)
            raise ValueError("boom")

        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(ValueError),
            self.env.cr.savepoint(),
        ):
            with self.patch_record(transport_cls, record_then_fail):
                self._reply()
        self.assertFalse(self.env["mail.conversation.sent.recipient"].search([]))

    def patch_record(self, cls, replacement):
        from unittest.mock import patch

        return patch.object(cls, "_record_sent_recipients", replacement)

    def test_reply_defaults_are_not_changed(self):
        message = self._reply(cc=["cc@example.com"])
        self.assertFalse(message.incoming_email_to)
        self.assertFalse(message.incoming_email_cc)
        self.assertFalse(message.outgoing_email_to)
        self.assertFalse(message.partner_ids)

    def test_other_models_serialize_as_before(self):
        partner_message = self.partner.message_post(body="<p>Hello</p>")
        payload = self._store_payload(partner_message)["mail.message"][0]
        self.assertNotIn("sent_recipients", payload)
