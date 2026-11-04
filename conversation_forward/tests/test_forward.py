# Acceptance criteria (forward-like-email):
#   AC12  forward one message or the whole conversation (chronological,
#         correspondent-visible messages only).
#   AC13  Fwd: subject (never doubled), quoted blocks, optional attachments.
#   AC14  to any address (no partner needed), only through the selected
#         transport's _send_raw; To required, valid addresses, sendable
#         transport.
#   AC15  Cc/Bcc reach the transport only; the record lists To/Cc, never Bcc.
#   AC16  recipients are never added as participants.
#   AC17  the forward record can never be the anchor of a later reply.
#   AC20  no mail.mail, no notification to followers/participants.

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import ForwardCommon


@tagged("post_install", "-at_install")
class TestForward(ForwardCommon):
    def _send_patch(self, transport=None):
        return patch.object(
            type(transport or self.transport),
            "_send_raw",
            autospec=True,
            return_value="<fwd-1@example.com>",
        )

    def test_forward_single_message_to_non_partner(self):
        partner_count = self.env["res.partner"].search_count([])
        with self.mock_mail_gateway(), self._send_patch() as send:
            self.conv._forward_messages(
                self.m2, ["stranger@example.com"], note="<p>FYI</p>"
            )
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], self.transport)
        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Fwd: Second question")
        self.assertEqual(kwargs["to_emails"], ["stranger@example.com"])
        body = str(kwargs["body"])
        for expected in (
            "FYI",
            "Forwarded message",
            "customer@example.com",
            "Second question",
            "Body two",
        ):
            self.assertIn(expected, body)
        self.assertEqual(
            [(a["filename"], a["content"]) for a in kwargs["attachments"]],
            [("spec.pdf", b"%PDF-spec")],
        )
        self.assertEqual(kwargs["in_reply_to"], "<m2@x>")
        self.assertFalse(self._new_mails)
        self.assertEqual(self.env["res.partner"].search_count([]), partner_count)

    def test_forward_subject_not_double_prefixed(self):
        for subject, expected in (
            ("Fwd: Quote", "Fwd: Quote"),
            ("FW: Quote", "FW: Quote"),
            ("Quote", "Fwd: Quote"),
        ):
            self.m2.subject = subject
            self.assertEqual(self.conv._forward_subject(self.m2), expected)

    def test_forward_without_attachments_toggle(self):
        with self._send_patch() as send:
            note = self.conv._forward_messages(
                self.m2, ["a@example.com"], include_attachments=False
            )
        self.assertEqual(send.call_args.kwargs["attachments"], [])
        self.assertFalse(note.attachment_ids)

    def test_forward_whole_conversation_chronological(self):
        with self._send_patch() as send:
            # a prior forward record must not be forwarded again
            self.conv._forward_messages(self.m1, ["a@example.com"])
            send.reset_mock()
            self.conv._forward_messages(None, ["a@example.com"])
        send.assert_called_once()
        body = str(send.call_args.kwargs["body"])
        positions = [body.index(text) for text in ("Body one", "Body two", "Our answer")]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("internal", body)
        self.assertNotIn("Forwarded via", body)
        self.assertEqual(body.count("Forwarded message"), 3)

    def test_forward_cc_bcc_reach_transport_only(self):
        with self.mock_mail_gateway(), self._send_patch() as send:
            note = self.conv._forward_messages(
                self.m2,
                ["a@example.com"],
                cc_emails=["b@example.com"],
                bcc_emails=["c@example.com"],
            )
        kwargs = send.call_args.kwargs
        self.assertEqual(kwargs["to_emails"], ["a@example.com"])
        self.assertEqual(kwargs["cc"], ["b@example.com"])
        self.assertEqual(kwargs["bcc"], ["c@example.com"])
        self.assertFalse(self._new_mails)
        self.assertEqual(note.subtype_id, self.env.ref("mail.mt_note"))
        self.assertFalse(note.transport_id)
        self.assertFalse(note.external_id)
        self.assertIn("a@example.com", note.body)
        self.assertIn("b@example.com", note.body)
        self.assertNotIn("c@example.com", note.body)
        self.assertEqual(note.attachment_ids, self.attachment)
        self.assertEqual(note.message_id, "<fwd-1@example.com>")

    @mute_logger("odoo.sql_db")
    def test_forward_requires_recipient_and_sendable_transport(self):
        with self._send_patch() as send:
            with self.assertRaises(UserError):
                self.conv._forward_messages(self.m2, [])
            with self.assertRaises(UserError):
                self.conv._forward_messages(self.m2, ["not an address"])
            with self.assertRaises(UserError):
                self.conv._forward_messages(self.m2, ["a@example.com"], cc_emails=["bad"])
            self.transport.sendable = False
            with self.assertRaises(UserError):
                self.conv._forward_messages(self.m2, ["a@example.com"])
        send.assert_not_called()

    def test_forward_uses_selected_transport_identity(self):
        other = self.env["conversation.transport"].create(
            {"name": "T2", "provider": False, "sendable": True, "login": "t2@example.com"}
        )
        with self._send_patch() as send:
            self.conv._forward_messages(self.m2, ["a@example.com"], transport=other)
        self.assertEqual(send.call_args.args[0], other)
        self.assertEqual(send.call_count, 1)
        # _send_raw has no From argument: the sender is always the
        # transport's own login, never the original author.
        self.assertNotIn("email_from", send.call_args.kwargs)
        self.assertNotIn("from_email", send.call_args.kwargs)

    def test_forward_recipients_not_participants(self):
        before = self.conv.participant_ids
        with self._send_patch():
            self.conv._forward_messages(
                self.m2,
                ["new1@example.com"],
                cc_emails=["new2@example.com"],
                bcc_emails=["new3@example.com"],
            )
        self.assertEqual(self.conv.participant_ids, before)

    def test_reply_after_forward_threads_with_correspondent(self):
        with self._send_patch() as forward_send:
            note = self.conv._forward_messages(self.m2, ["a@example.com"])
        with patch.object(
            type(self.transport), "_is_email_transport", return_value=True
        ), patch.object(
            type(self.transport), "_send_raw", autospec=True, return_value="<r@x>"
        ) as reply_send:
            self.conv.action_reply("<p>hi</p>", recipients=["customer@example.com"])
        forward_send.assert_called_once()
        in_reply_to = reply_send.call_args.kwargs["in_reply_to"]
        self.assertEqual(in_reply_to, "<m3@x>")
        self.assertNotEqual(in_reply_to, note.message_id)
        self.assertNotEqual(in_reply_to, "<fwd-1@example.com>")

    def test_forward_whole_conversation_threads_under_latest_message(self):
        with self._send_patch() as send:
            self.conv._forward_messages(None, ["a@example.com"])
        # m3 is the latest forwardable message of the default set.
        self.assertEqual(send.call_args.kwargs["in_reply_to"], "<m3@x>")

    def test_forward_explicit_set_threads_under_its_latest_by_date_then_id(self):
        # Passed out of order: the latest is chosen after the (date, id) sort.
        with self._send_patch() as send:
            self.conv._forward_messages(self.m2 | self.m1, ["a@example.com"])
        self.assertEqual(send.call_args.kwargs["in_reply_to"], "<m2@x>")

    def test_forward_threads_on_message_id_never_external_id(self):
        self.assertNotEqual(self.m2.external_id, self.m2.message_id)
        with self._send_patch() as send:
            self.conv._forward_messages(self.m2, ["a@example.com"])
        self.assertEqual(send.call_args.kwargs["in_reply_to"], "<m2@x>")

    def test_forward_without_message_id_sends_no_threading_header(self):
        self.m2.message_id = False
        with self._send_patch() as send:
            note = self.conv._forward_messages(self.m2, ["a@example.com"])
        self.assertIsNone(send.call_args.kwargs["in_reply_to"])
        self.assertEqual(note.message_id, "<fwd-1@example.com>")

    def test_forward_stays_a_quiet_note_with_wire_id(self):
        with self.mock_mail_gateway(), self._send_patch():
            note = self.conv._forward_messages(
                self.m2, ["a@example.com"], cc_emails=["c@example.com"],
                bcc_emails=["secret@example.com"],
            )
        self.assertEqual(note.subtype_id, self.env.ref("mail.mt_note"))
        self.assertEqual(note.message_id, "<fwd-1@example.com>")
        self.assertFalse(note.transport_id)
        self.assertFalse(note.external_id)
        self.assertIn("To: a@example.com", str(note.body))
        self.assertIn("Cc: c@example.com", str(note.body))
        self.assertNotIn("secret@example.com", str(note.body))
        self.assertFalse(self._new_mails)

    def test_reply_after_threaded_forward_still_anchors_on_correspondent(self):
        with self._send_patch():
            note = self.conv._forward_messages(None, ["a@example.com"])
        self.assertEqual(note.message_id, "<fwd-1@example.com>")
        with patch.object(
            type(self.transport), "_is_email_transport", return_value=True
        ), patch.object(
            type(self.transport), "_send_raw", autospec=True, return_value="<r@x>"
        ) as reply_send:
            self.conv.action_reply("<p>hi</p>", recipients=["customer@example.com"])
        self.assertEqual(reply_send.call_args.kwargs["in_reply_to"], "<m3@x>")

    def test_threading_id_reaches_the_built_email_headers(self):
        """End to end through the email transport's real ``_send_raw``: the
        header lands on the built message, and Bcc stays out of it."""
        sent = []
        connection = MagicMock()
        connection.send_message.side_effect = lambda msg, to_addrs=None: sent.append(
            (msg, to_addrs)
        )

        @contextmanager
        def fake_smtp(*args, **kwargs):
            yield connection

        transport_cls = type(self.transport)
        with patch.object(
            transport_cls, "_is_email_transport", return_value=True
        ), patch.object(
            transport_cls, "_smtp_connection", side_effect=fake_smtp
        ), patch.object(
            transport_cls, "_imap_append_to_sent", return_value=False
        ):
            note = self.conv._forward_messages(
                self.m2, ["a@example.com"], bcc_emails=["secret@example.com"]
            )
        self.assertEqual(len(sent), 1)
        outgoing, envelope = sent[0]
        self.assertEqual(outgoing["In-Reply-To"], "<m2@x>")
        self.assertIn("<m2@x>", outgoing["References"])
        self.assertIsNone(outgoing["Bcc"])
        self.assertNotIn("secret@example.com", outgoing.as_string())
        self.assertIn("secret@example.com", envelope)
        self.assertEqual(note.message_id, outgoing["Message-Id"])

    def test_long_threading_id_goes_out_plain_on_the_wire(self):
        """A Message-Id longer than the 78-character line length (the
        normal length of an Odoo- or Exchange-generated id) still goes out
        as the plain token in In-Reply-To and References: never an RFC 2047
        encoded word, never folded inside the id."""
        long_id = (
            "<123456789012345.1234567890.123456789012345-openerp-7-mail."
            "conversation@mail-host-0123456789.example.com>"
        )
        self.assertGreater(len(long_id), 78)
        self.m2.message_id = long_id
        sent = []
        connection = MagicMock()
        connection.send_message.side_effect = lambda msg, to_addrs=None: sent.append(
            msg
        )

        @contextmanager
        def fake_smtp(*args, **kwargs):
            yield connection

        transport_cls = type(self.transport)
        with patch.object(
            transport_cls, "_is_email_transport", return_value=True
        ), patch.object(
            transport_cls, "_smtp_connection", side_effect=fake_smtp
        ), patch.object(
            transport_cls, "_imap_append_to_sent", return_value=False
        ):
            self.conv._forward_messages(self.m2, ["a@example.com"])
        self.assertEqual(len(sent), 1)
        raw = sent[0].as_bytes(policy=sent[0].policy.clone(linesep="\r\n"))
        head = raw.split(b"\r\n\r\n", 1)[0]
        lines = head.split(b"\r\n")
        self.assertIn(b"In-Reply-To: " + long_id.encode(), lines)
        self.assertIn(b"References: " + long_id.encode(), lines)
        # No encoded word anywhere in the (all-ASCII) header block.
        self.assertNotIn(b"=?", head)
