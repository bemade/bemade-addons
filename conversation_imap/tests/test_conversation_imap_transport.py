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
#   Blocking issue #1 (2026-08-13 redo): _imap_connection authenticates
#     with XOAUTH2 instead of a password when a provider's
#     _imap_oauth_string hook returns one (conversation_gmail's is the
#     concrete case, exercised end to end in its own tests; this covers
#     the generic dispatch conversation_imap itself owns), and retries
#     exactly once -- with a freshly-refreshed token -- on an auth
#     failure. The base "configure the IMAP host and login" guard is
#     unchanged either way.

import imaplib
from pathlib import Path
from unittest.mock import patch

from odoo.exceptions import UserError
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

    def test_normalize_sanitizes_html_part(self):
        # Blocking issue #2: an inbound HTML body is untrusted input --
        # <script>/inline event handlers must never survive into the
        # inbox viewer, sanitized through Odoo's own html_sanitize.
        raw = {
            "external_id": "8",
            "rfc822": _read_fixture("html_script_injection.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertNotIn("<script", stub["body"])
        self.assertNotIn("onerror", stub["body"])
        self.assertIn("Click", stub["body"])

    def test_normalize_multipart_mixed_lists_attachment_not_inlined(self):
        # Blocking issue #2: multipart/mixed with an attachment -- the
        # body is the multipart/alternative part (get_body() skips the
        # attachment), and the attachment is listed as metadata, never
        # its encoded payload inlined into the body.
        raw = {
            "external_id": "9",
            "rfc822": _read_fixture("multipart_mixed_with_attachment.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertIn("invoice", stub["body"])
        self.assertNotIn("JVBERi0", stub["body"])  # no base64 payload inlined
        self.assertEqual(len(stub["attachments"]), 1)
        attachment = stub["attachments"][0]
        self.assertEqual(attachment["filename"], "invoice.pdf")
        self.assertEqual(attachment["content_type"], "application/pdf")
        self.assertGreater(attachment["size"], 0)

    def test_normalize_decodes_quoted_printable(self):
        raw = {
            "external_id": "10",
            "rfc822": _read_fixture("quoted_printable.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertIn("café préféré", stub["body"])
        self.assertIn("livraison prévue", stub["body"])

    def test_normalize_decodes_non_utf8_charset(self):
        raw = {
            "external_id": "11",
            "rfc822": _read_fixture("non_utf8_charset.eml"),
        }
        stub = self.transport._normalize(raw)
        self.assertIn("commande a été confirmée", stub["body"])

    def test_normalize_simple_message_has_no_attachments(self):
        raw = {"external_id": "7", "rfc822": _read_fixture("bare_email_no_partner.eml")}
        stub = self.transport._normalize(raw)
        self.assertEqual(stub["attachments"], [])


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


class FakeOAuthIMAP:
    """Records auth calls; simulates a first-attempt auth failure to
    exercise the token-refresh-then-retry path."""

    fail_once = False
    authenticate_calls = []

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def authenticate(self, mechanism, callback):
        FakeOAuthIMAP.authenticate_calls.append((mechanism, callback(b"")))
        if FakeOAuthIMAP.fail_once and len(FakeOAuthIMAP.authenticate_calls) == 1:
            raise imaplib.IMAP4.error("token expired")

    def select(self, folder):
        pass

    def close(self):
        pass

    def logout(self):
        pass


class TestConversationImapOAuthConnection(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "OAuth-Capable IMAP Transport",
                "provider": "imap",
                "browsable": True,
                "login": "oauth-user@example.com",
                "imap_host": "imap.example.com",
            }
        )

    def setUp(self):
        super().setUp()
        FakeOAuthIMAP.authenticate_calls = []
        FakeOAuthIMAP.fail_once = False
        patcher = patch.object(
            type(self.transport), "_get_imap_client_class", return_value=FakeOAuthIMAP
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_oauth_string_used_instead_of_password_login(self):
        oauth_patcher = patch.object(
            type(self.transport),
            "_imap_oauth_string",
            return_value="user=oauth-user@example.com\1auth=Bearer token\1\1",
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)
        with self.transport._imap_connection():
            pass
        self.assertEqual(len(FakeOAuthIMAP.authenticate_calls), 1)
        mechanism, sasl_response = FakeOAuthIMAP.authenticate_calls[0]
        self.assertEqual(mechanism, "XOAUTH2")
        self.assertIn(b"Bearer token", sasl_response)

    def test_auth_failure_refreshes_token_and_retries_once(self):
        FakeOAuthIMAP.fail_once = True
        calls = []

        def _oauth_string(self, force_refresh=False):
            calls.append(force_refresh)
            token = "refreshed-token" if force_refresh else "stale-token"
            return "user=oauth-user@example.com\1auth=Bearer %s\1\1" % token

        oauth_patcher = patch.object(
            type(self.transport), "_imap_oauth_string", _oauth_string
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)
        with self.transport._imap_connection():
            pass
        self.assertEqual(len(FakeOAuthIMAP.authenticate_calls), 2)
        self.assertIn(b"Bearer stale-token", FakeOAuthIMAP.authenticate_calls[0][1])
        self.assertIn(
            b"Bearer refreshed-token", FakeOAuthIMAP.authenticate_calls[1][1]
        )
        self.assertEqual(calls, [False, True])

    def test_no_oauth_string_falls_back_to_password_guard_unchanged(self):
        # No _imap_oauth_string override and no imap_host/login on a
        # fresh transport -- the original guard fires verbatim.
        bare = self.env["conversation.transport"].create(
            {"name": "Bare IMAP", "provider": "imap"}
        )
        with self.assertRaises(UserError):
            with bare._imap_connection():
                pass


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
