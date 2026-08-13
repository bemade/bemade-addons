# Acceptance criteria (task #3965, conversation_gmail):
#   Test plan #7 (Gmail auth, mocked): with a mocked XOAUTH2 token from
#     google.gmail.mixin, the transport builds an auth string and stores
#     no password anywhere.
#   Normalize/send smoke: the same conversation_base.tools.mime pipeline
#     conversation_imap uses is wired correctly here too (shared, not
#     duplicated), and _send authenticates over SMTP with AUTH XOAUTH2
#     rather than a plain login.
#   Staging-review fix (2026-08-13): "Connect to Gmail" dead-ended for an
#     admin when the instance-level OAuth Client ID/Secret were never
#     configured -- open_google_gmail_uri() must redirect an admin
#     straight to General Settings with an actionable message instead of
#     a bare "configure your credentials" error, while leaving the
#     mixin's own AccessError for non-admins untouched.

from unittest.mock import patch

from odoo.exceptions import AccessError, RedirectWarning
from odoo.fields import Command
from odoo.tests import TransactionCase


class TestConversationGmailNoPassword(TransactionCase):
    def test_no_password_field_on_gmail_provider(self):
        self.assertNotIn("password", self.env["conversation.transport"]._fields)


class TestConversationGmailOAuth2(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Test Transport",
                "provider": "gmail",
                "browsable": True,
                "sendable": True,
                "login": "durpro@gmail.com",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )

    def test_oauth2_string_built_from_mixin_without_network_call(self):
        with patch.object(
            type(self.transport),
            "_generate_oauth2_string",
            return_value="user=durpro@gmail.com\1auth=Bearer fake-access-token\1\1",
            autospec=True,
        ) as mocked:
            auth_string = self.transport._gmail_oauth2_string()
        mocked.assert_called_once_with(
            self.transport, "durpro@gmail.com", "fake-refresh-token"
        )
        self.assertIn("Bearer fake-access-token", auth_string)

    def test_oauth2_string_requires_connected_account(self):
        from odoo.exceptions import UserError

        disconnected = self.env["conversation.transport"].create(
            {
                "name": "Not Connected",
                "provider": "gmail",
                "login": "someone@gmail.com",
            }
        )
        with self.assertRaises(UserError):
            disconnected._gmail_oauth2_string()


class FakeGmailSMTP:
    """Records the AUTH XOAUTH2 command and the outgoing message instead
    of opening a real socket."""

    sent = []
    auth_commands = []

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def starttls(self):
        pass

    def docmd(self, command, args=""):
        FakeGmailSMTP.auth_commands.append((command, args))
        return 235, b"Authentication successful"

    def send_message(self, message):
        FakeGmailSMTP.sent.append(message)

    def quit(self):
        pass


class TestConversationGmailSend(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Send Transport",
                "provider": "gmail",
                "sendable": True,
                "login": "durpro@gmail.com",
                "google_gmail_refresh_token": "fake-refresh-token",
            }
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Gmail Conversation", "primary_transport_id": cls.transport.id}
        )

    def setUp(self):
        super().setUp()
        FakeGmailSMTP.sent = []
        FakeGmailSMTP.auth_commands = []
        smtp_patcher = patch.object(
            type(self.transport),
            "_get_smtp_client_class",
            return_value=FakeGmailSMTP,
        )
        smtp_patcher.start()
        self.addCleanup(smtp_patcher.stop)
        oauth_patcher = patch.object(
            type(self.transport),
            "_generate_oauth2_string",
            return_value="user=durpro@gmail.com\1auth=Bearer fake-access-token\1\1",
            autospec=True,
        )
        oauth_patcher.start()
        self.addCleanup(oauth_patcher.stop)

    def test_send_authenticates_with_xoauth2_not_a_password(self):
        message = self.conversation.action_reply(
            "<p>Reply via Gmail</p>", recipients=["someone@example.com"]
        )
        self.assertEqual(len(FakeGmailSMTP.sent), 1)
        self.assertEqual(len(FakeGmailSMTP.auth_commands), 1)
        command, args = FakeGmailSMTP.auth_commands[0]
        self.assertEqual(command, "AUTH")
        self.assertTrue(args.startswith("XOAUTH2 "))
        self.assertEqual(message.transport_id, self.transport)


class TestConversationGmailConnectRedirect(TransactionCase):
    """UAT gap (2026-08-13, task #3965): clicking "Connect to Gmail" with
    no instance-level OAuth Client ID/Secret configured must point the
    admin at where to configure it, not dead-end on a bare error."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Gmail Redirect Test",
                "provider": "gmail",
                "login": "durpro@gmail.com",
            }
        )
        cls.admin = cls.env["res.users"].create(
            {
                "name": "Test System Admin",
                "login": "test-gmail-oauth-admin@example.com",
                "groups_id": [Command.link(cls.env.ref("base.group_system").id)],
            }
        )
        cls.internal_user = cls.env["res.users"].create(
            {
                "name": "Test Internal User",
                "login": "test-gmail-oauth-user@example.com",
                "groups_id": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )

    def setUp(self):
        super().setUp()
        # Each test runs in its own rolled-back savepoint (TransactionCase),
        # so clearing these here never leaks between tests.
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "")
        config.set_param("google_gmail_client_secret", "")

    def test_admin_without_credentials_gets_redirected_to_settings(self):
        with self.assertRaises(RedirectWarning) as capture:
            self.transport.with_user(self.admin).open_google_gmail_uri()
        message, action_id, button_text, _context = capture.exception.args
        self.assertIn("General Settings", message)
        self.assertEqual(button_text, "Go to General Settings")
        self.assertEqual(
            action_id,
            self.env.ref("base_setup.action_general_configuration").id,
        )

    def test_admin_with_credentials_falls_through_to_mixin(self):
        config = self.env["ir.config_parameter"].sudo()
        config.set_param("google_gmail_client_id", "fake-client-id")
        config.set_param("google_gmail_client_secret", "fake-client-secret")
        action = self.transport.with_user(self.admin).open_google_gmail_uri()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertIn("accounts.google.com", action["url"])

    def test_non_admin_keeps_original_access_error(self):
        with self.assertRaises(AccessError):
            self.transport.with_user(self.internal_user).open_google_gmail_uri()
