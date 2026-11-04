# Acceptance criteria (conversation_email_base, outbound threading headers):
#   1. In-Reply-To and References go on the wire as the plain <msg-id>,
#      whatever its length: never an RFC 2047 encoded word and never folded
#      inside the id. A mail client compares the raw token against the
#      Message-Ids it knows, so an encoded id does not thread. Ids longer
#      than the 78-character line length are ordinary (Odoo's own ids,
#      Exchange/Outlook ids), so the tests use one of 110 characters.
#   2. This holds on both paths through the send primitive: a direct
#      ``_send_raw`` call (what a forward makes) and ``_send`` (a reply,
#      anchored on the latest transport-borne message's Message-Id).
#   3. The message's own long Message-Id is plain as well.

from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase

LONG_ID = (
    "<123456789012345.1234567890.123456789012345-openerp-7-mail.conversation"
    "@mail-host-0123456789.example.com>"
)
OWN_ID = (
    "<987654321098765.9876543210.987654321098765-openerp-9-mail.conversation"
    "@mail-host-0123456789.example.com>"
)


class TestConversationEmailSendHeaders(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Mailbox",
                "provider": False,
                "sendable": True,
                "login": "me@example.com",
            }
        )

    def setUp(self):
        super().setUp()
        self.sent = []
        connection = MagicMock()
        connection.send_message.side_effect = (
            lambda msg, to_addrs=None: self.sent.append(msg)
        )

        @contextmanager
        def fake_smtp(*args, **kwargs):
            yield connection

        transport_cls = type(self.transport)
        for patcher in (
            patch.object(transport_cls, "_is_email_transport", return_value=True),
            patch.object(transport_cls, "_smtp_connection", side_effect=fake_smtp),
            patch.object(transport_cls, "_imap_append_to_sent", return_value=False),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _wire_headers(self):
        """The header block exactly as it is put on the wire."""
        self.assertEqual(len(self.sent), 1)
        raw = self.sent[0].as_bytes(policy=self.sent[0].policy.clone(linesep="\r\n"))
        return raw.split(b"\r\n\r\n", 1)[0].split(b"\r\n")

    def _assert_plain(self, lines, name, msg_id):
        prefix = name.encode() + b":"
        found = [line for line in lines if line.startswith(prefix)]
        self.assertEqual(found, [prefix + b" " + msg_id.encode()])
        # Not continued on a following (folded) line either.
        index = lines.index(found[0])
        if index + 1 < len(lines):
            self.assertFalse(lines[index + 1][:1].isspace())

    def test_send_raw_keeps_long_threading_id_plain(self):
        self.assertGreater(len(LONG_ID), 78)
        self.transport._send_raw(
            subject="Fwd: question",
            body="<p>x</p>",
            to_emails=["a@example.com"],
            in_reply_to=LONG_ID,
        )
        lines = self._wire_headers()
        self._assert_plain(lines, "In-Reply-To", LONG_ID)
        self._assert_plain(lines, "References", LONG_ID)
        self.assertNotIn(b"=?", b"\r\n".join(lines))
        self.assertEqual(self.sent[0]["In-Reply-To"], LONG_ID)

    def test_reply_anchored_on_long_id_keeps_it_plain(self):
        conversation = self.env["mail.conversation"].create(
            {"name": "Thread", "primary_transport_id": self.transport.id}
        )
        anchor = conversation.message_post(body="<p>question</p>")
        anchor.write({"external_id": "227398", "message_id": LONG_ID})
        reply = conversation.message_post(body="<p>answer</p>")
        reply.message_id = OWN_ID
        self.transport._send(conversation, reply, recipients=["c@example.com"])
        lines = self._wire_headers()
        self._assert_plain(lines, "In-Reply-To", LONG_ID)
        self._assert_plain(lines, "References", LONG_ID)
        self._assert_plain(lines, "Message-Id", OWN_ID)
        self.assertNotIn(b"=?", b"\r\n".join(lines))

    def _two_inbound(self):
        conversation = self.env["mail.conversation"].create(
            {"name": "Thread", "primary_transport_id": self.transport.id}
        )
        first = conversation.message_post(body="<p>first question</p>")
        first.write({"external_id": "1", "message_id": "<first@client.example>"})
        second = conversation.message_post(body="<p>second question</p>")
        second.write({"external_id": "2", "message_id": "<second@client.example>"})
        return conversation, first, second

    def test_reply_to_a_specific_message_threads_under_it(self):
        conversation, first, _second = self._two_inbound()
        reply = conversation.action_reply(
            "<p>answer to the first</p>",
            recipients=["c@example.com"],
            reply_to_message=first,
        )
        lines = self._wire_headers()
        self._assert_plain(lines, "In-Reply-To", "<first@client.example>")
        self._assert_plain(lines, "References", "<first@client.example>")
        self.assertEqual(reply.parent_id, first)

    def test_reply_without_a_target_keeps_the_newest_anchor(self):
        conversation, _first, second = self._two_inbound()
        conversation.action_reply("<p>answer</p>", recipients=["c@example.com"])
        lines = self._wire_headers()
        self._assert_plain(lines, "In-Reply-To", "<second@client.example>")
        self._assert_plain(lines, "References", "<second@client.example>")

    def test_a_target_from_another_conversation_is_not_trusted(self):
        conversation, _first, _second = self._two_inbound()
        other = self.env["mail.conversation"].create(
            {"name": "Other", "primary_transport_id": self.transport.id}
        )
        stranger = other.message_post(body="<p>elsewhere</p>")
        stranger.write({"external_id": "9", "message_id": "<stranger@client.example>"})
        transport = self.transport.with_context(
            conversation_reply_to_message_id=stranger.id
        )
        self.assertFalse(transport._explicit_reply_message_id(conversation))

    def test_send_raw_stamps_exactly_one_date_header(self):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        self.transport._send_raw(
            subject="Hello",
            body="<p>x</p>",
            to_emails=["a@example.com"],
            bcc=["hidden@example.com"],
        )
        after = datetime.now(timezone.utc)
        lines = self._wire_headers()
        dates = [line for line in lines if line.startswith(b"Date:")]
        self.assertEqual(len(dates), 1)
        sent_at = parsedate_to_datetime(self.sent[0]["Date"])
        self.assertLessEqual(before, sent_at)
        self.assertLessEqual(sent_at, after)
        # Bcc stays out of the headers.
        self.assertFalse([line for line in lines if line.startswith(b"Bcc")])

    def test_sent_folder_copy_carries_the_same_date(self):
        appended = []
        with patch.object(
            type(self.transport),
            "_imap_append_to_sent",
            side_effect=lambda outgoing: appended.append(outgoing),
        ):
            self.transport._send_raw(
                subject="Hello", body="<p>x</p>", to_emails=["a@example.com"]
            )
        self.assertEqual(len(appended), 1)
        self.assertTrue(appended[0]["Date"])
        self.assertEqual(appended[0]["Date"], self.sent[0]["Date"])
        self.assertEqual(appended[0]["Message-Id"], self.sent[0]["Message-Id"])
