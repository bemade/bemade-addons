# Acceptance criteria (conversation_email_base, SMTP connection modes):
#   1. ``ssl`` opens an implicit-TLS client (SMTP_SSL semantics) and never
#      calls ``starttls()``; ``starttls`` connects plain, then calls
#      ``starttls()`` once; ``none`` does neither.
#   2. Every mode opens the connection with the engine's socket timeout.
#   3. Providers that only return the older ``smtp_starttls`` boolean
#      (Gmail) keep their behaviour.

from unittest.mock import patch

from odoo.tests import TransactionCase


class FakeSmtp:
    """Records how it was built and used; stands in for smtplib.SMTP."""

    instances = []
    kind = "plain"

    def __init__(self, host, port, timeout=None):
        self.args = (host, port)
        self.timeout = timeout
        self.calls = []
        type(self).instances.append(self)

    def starttls(self):
        self.calls.append("starttls")

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def quit(self):
        self.calls.append("quit")


class FakeSmtpSsl(FakeSmtp):
    kind = "ssl"
    instances = []


class TestConversationEmailSmtpModes(TransactionCase):
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
        FakeSmtp.instances = []
        FakeSmtpSsl.instances = []
        cls = type(self.transport)
        for patcher in (
            patch.object(cls, "_get_smtp_client_class", return_value=FakeSmtp),
            patch.object(cls, "_get_smtp_ssl_client_class", return_value=FakeSmtpSsl),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _connect(self, **extra):
        params = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 465,
            "password": "secret",
            **extra,
        }
        with patch.object(
            type(self.transport), "_email_connection_params", return_value=params
        ):
            with self.transport._smtp_connection() as connection:
                return connection

    def test_ssl_uses_implicit_tls_client_and_never_starttls(self):
        connection = self._connect(smtp_encryption="ssl")
        self.assertEqual(FakeSmtp.instances, [])
        self.assertEqual(FakeSmtpSsl.instances, [connection])
        self.assertEqual(connection.args, ("smtp.example.com", 465))
        self.assertNotIn("starttls", connection.calls)
        self.assertIn(("login", "me@example.com", "secret"), connection.calls)
        self.assertEqual(connection.calls[-1], "quit")

    def test_starttls_connects_plain_then_upgrades(self):
        connection = self._connect(smtp_encryption="starttls", smtp_port=587)
        self.assertEqual(FakeSmtpSsl.instances, [])
        self.assertEqual(connection.args, ("smtp.example.com", 587))
        self.assertEqual(connection.calls.count("starttls"), 1)
        self.assertLess(
            connection.calls.index("starttls"),
            connection.calls.index(("login", "me@example.com", "secret")),
        )

    def test_none_uses_neither_tls_nor_ssl_client(self):
        connection = self._connect(smtp_encryption="none", smtp_port=25)
        self.assertEqual(FakeSmtpSsl.instances, [])
        self.assertNotIn("starttls", connection.calls)
        self.assertIn(("login", "me@example.com", "secret"), connection.calls)

    def test_every_mode_keeps_the_socket_timeout(self):
        expected = self.transport._email_socket_timeout()
        self.assertTrue(expected)
        for mode in ("none", "starttls", "ssl"):
            connection = self._connect(smtp_encryption=mode)
            self.assertEqual(connection.timeout, expected, mode)

    def test_legacy_starttls_boolean_still_selects_the_mode(self):
        starttls = self._connect(smtp_starttls=True, smtp_port=587)
        self.assertEqual(starttls.calls.count("starttls"), 1)
        plain = self._connect(smtp_starttls=False, smtp_port=25)
        self.assertNotIn("starttls", plain.calls)
        # Neither key at all: STARTTLS, as before.
        default = self._connect(smtp_port=587)
        self.assertEqual(default.calls.count("starttls"), 1)
