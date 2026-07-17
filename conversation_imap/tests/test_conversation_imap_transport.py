# Acceptance criteria (task #3965, conversation_imap):
#   Test plan #1 (_normalize ETL): a fixture .eml normalizes to the
#     canonical dict; covers the non-obvious parses -- a multipart body
#     (HTML preferred) and a bare-email From with no partner. Also guards
#     the plaintext-body escaping fix (a plaintext body must never be
#     raw-interpolated into the HTML message body).
#   Test plan #2 (_match_inbound correlation): a raw whose
#     References/In-Reply-To matches an existing message's external_id
#     returns that conversation's message; an unknown raw returns falsy; a
#     match is never returned across a different transport.
#   Test plan #6 (outbound _send): a stub transport whose _send is
#     captured records the outbound mail.message with transport_id +
#     external_id, delivered to the explicit recipient list.
#   Test plan #9 (view smoke): Form on the imap-extended transport config
#     view builds (guards missing view fields).

from pathlib import Path
from unittest.mock import patch

from odoo.tests import Form, TransactionCase

FIXTURES = Path(__file__).parent / "fixtures"


def _read_fixture(name):
    return (FIXTURES / name).read_bytes()


class TestConversationImapNormalize(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "IMAP Test Transport",
                "provider": "imap",
                "browsable": True,
                "searchable": True,
                "sendable": True,
                "login": "sales@example.com",
                "imap_host": "imap.example.com",
                "smtp_host": "smtp.example.com",
            }
        )

    def test_normalize_multipart_prefers_html_and_captures_references(self):
        raw = {"external_id": "42", "rfc822": _read_fixture("multipart_reply.eml")}
        stub = self.transport._normalize(raw)
        self.assertEqual(stub["email_from"], "customer@example.com")
        self.assertEqual(stub["to"], ["sales@example.com"])
        self.assertEqual(stub["cc"], ["watcher@example.com"])
        self.assertIn("<p>Thanks, that works for us.</p>", stub["body"])
        self.assertEqual(stub["in_reply_to"], "<original-msg-1@example.com>")
        self.assertIn("<thread-root@example.com>", stub["references"])
        self.assertEqual(stub["external_id"], "42")

    def test_normalize_bare_email_no_partner_escapes_plaintext(self):
        raw = {"external_id": "7", "rfc822": _read_fixture("bare_email_no_partner.eml")}
        stub = self.transport._normalize(raw)
        self.assertEqual(stub["email_from"], "stranger@example.com")
        # A plaintext body's own markup must never be interpolated raw into
        # the HTML message body -- it would otherwise be stored/rendered
        # unescaped in the conversation's chatter.
        self.assertNotIn("<script>", stub["body"])
        self.assertIn("&lt;script&gt;", stub["body"])


class TestConversationImapMatchInbound(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "IMAP Transport A", "provider": "imap", "login": "a@example.com"}
        )
        cls.other_transport = cls.env["conversation.transport"].create(
            {"name": "IMAP Transport B", "provider": "imap", "login": "b@example.com"}
        )
        cls.conversation = cls.env["mail.conversation"].create({"name": "Thread"})

    def _post_with_external_id(self, transport, external_id):
        message = self.conversation.message_post(
            body="prior message", subtype_xmlid="mail.mt_note"
        )
        message.write({"transport_id": transport.id, "external_id": external_id})
        return message

    def test_match_inbound_finds_message_within_same_transport(self):
        self._post_with_external_id(self.transport, "<original-msg-1@example.com>")
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertTrue(matched)
        self.assertEqual(matched.transport_id, self.transport)

    def test_match_inbound_never_crosses_transport(self):
        # The matching external_id exists, but only on a DIFFERENT
        # transport -- correlation must stay within-transport.
        self._post_with_external_id(
            self.other_transport, "<original-msg-1@example.com>"
        )
        raw = {"rfc822": _read_fixture("multipart_reply.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertFalse(matched)

    def test_match_inbound_unknown_returns_falsy(self):
        raw = {"rfc822": _read_fixture("bare_email_no_partner.eml")}
        matched = self.transport._match_inbound(raw)
        self.assertFalse(matched)


class FakeSMTP:
    """Records the outgoing message instead of opening a real socket."""

    sent = []

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        FakeSMTP.sent.append(message)

    def quit(self):
        pass


class TestConversationImapSend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "IMAP Send Transport",
                "provider": "imap",
                "sendable": True,
                "login": "sales@example.com",
                "smtp_host": "smtp.example.com",
            }
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Send Conversation", "primary_transport_id": cls.transport.id}
        )

    def setUp(self):
        super().setUp()
        FakeSMTP.sent = []
        patcher = patch.object(
            type(self.transport), "_get_smtp_client_class", return_value=FakeSMTP
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_send_delivers_to_explicit_recipients_and_records_metadata(self):
        message = self.conversation.action_reply(
            "<p>Here you go</p>", recipients=["explicit@example.com"]
        )
        self.assertEqual(len(FakeSMTP.sent), 1)
        outgoing = FakeSMTP.sent[0]
        self.assertEqual(str(outgoing["To"]), "explicit@example.com")
        self.assertEqual(message.transport_id, self.transport)
        self.assertTrue(message.external_id)


class TestConversationImapViewSmoke(TransactionCase):
    def test_form_builds_with_imap_fields(self):
        with Form(self.env["conversation.transport"]) as form:
            form.name = "Smoke Transport"
            form.provider = "imap"
            form.imap_host = "imap.example.com"
            form.smtp_host = "smtp.example.com"
            form.password = "secret"
        transport = form.save()
        self.assertEqual(transport.imap_host, "imap.example.com")
