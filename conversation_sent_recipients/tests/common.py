from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase


class SentRecipientsCommon(TransactionCase):
    """A sendable email transport whose SMTP connection is replaced by a
    recorder, so the headers and the envelope that really go out can be
    compared with what the conversation shows."""

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
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Delivery question", "primary_transport_id": cls.transport.id}
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Customer Person", "email": "customer@example.com"}
        )
        cls.env["mail.conversation.participant"].create(
            {
                "conversation_id": cls.conversation.id,
                "partner_id": cls.partner.id,
                "email": "customer@example.com",
                "role": "requester",
            }
        )

    def setUp(self):
        super().setUp()
        self.sent = []
        self.envelopes = []
        connection = MagicMock()

        def send_message(msg, to_addrs=None):
            self.sent.append(msg)
            self.envelopes.append(list(to_addrs or []))

        connection.send_message.side_effect = send_message

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

    def _recorded(self, message):
        return [
            (rec.mode, rec.email)
            for rec in self.env["mail.conversation.sent.recipient"].search(
                [("message_id", "=", message.id)]
            )
        ]

    def _store_payload(self, message):
        from odoo.addons.mail.tools.discuss import Store

        store = Store().add(message)
        return store.get_result()
