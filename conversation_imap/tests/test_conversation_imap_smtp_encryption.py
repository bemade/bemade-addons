# Acceptance criteria (conversation_imap, SMTP encryption choice):
#   1. A mailbox offers none / STARTTLS / SSL/TLS and defaults to STARTTLS.
#   2. The choice reaches the engine through the connection params.
#   3. Mailboxes configured before the upgrade keep their behaviour:
#      the old checkbox True -> STARTTLS, False -> none.

import importlib.util
import pathlib

from odoo.tests import Form, TransactionCase


class TestConversationImapSmtpEncryption(TransactionCase):
    def _transport(self, **extra):
        return self.env["conversation.transport"].create(
            {
                "name": "Enc Transport",
                "provider": "imap",
                "login": "me@example.com",
                "smtp_host": "smtp.example.com",
                **extra,
            }
        )

    def test_new_transport_defaults_to_starttls_on_587(self):
        transport = self._transport()
        self.assertEqual(transport.smtp_encryption, "starttls")
        self.assertEqual(transport.smtp_port, 587)

    def test_params_carry_each_mode(self):
        for mode in ("none", "starttls", "ssl"):
            transport = self._transport(smtp_encryption=mode, smtp_port=465)
            params = transport._email_connection_params()
            self.assertEqual(params["smtp_encryption"], mode)
            self.assertEqual(params["smtp_port"], 465)

    def test_legacy_checkbox_still_maps_onto_the_choice(self):
        self.assertEqual(self._transport(smtp_ssl=False).smtp_encryption, "none")
        self.assertEqual(self._transport(smtp_ssl=True).smtp_encryption, "starttls")

    def test_form_offers_the_three_modes(self):
        with Form(self.env["conversation.transport"]) as form:
            form.name = "Form Transport"
            form.provider = "imap"
            form.smtp_host = "smtp.example.com"
            form.smtp_port = 465
            self.assertEqual(form.smtp_encryption, "starttls")
            form.smtp_encryption = "ssl"
        transport = form.save()
        self.assertEqual(transport.smtp_encryption, "ssl")
        selection = dict(
            self.env["conversation.transport"]._fields["smtp_encryption"].selection
        )
        self.assertEqual(set(selection), {"none", "starttls", "ssl"})


class TestConversationImapSmtpMigration(TransactionCase):
    def _migrate(self):
        path = (
            pathlib.Path(__file__).resolve().parent.parent
            / "migrations"
            / "19.0.1.4.0"
            / "pre-migrate.py"
        )
        spec = importlib.util.spec_from_file_location("imap_pre_migrate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.1.3.2")

    def test_legacy_values_become_the_matching_mode(self):
        cr = self.env.cr
        names = {"on": "Legacy On", "off": "Legacy Off", "null": "Legacy Null"}
        ids = {
            key: self.env["conversation.transport"]
            .create({"name": name, "provider": "imap"})
            .id
            for key, name in names.items()
        }
        self.env.flush_all()
        # Recreate the pre-upgrade schema: the old column in, the new one out.
        cr.execute("ALTER TABLE conversation_transport ADD COLUMN smtp_ssl boolean")
        cr.execute("ALTER TABLE conversation_transport DROP COLUMN smtp_encryption")
        cr.execute(
            "UPDATE conversation_transport SET smtp_ssl = TRUE WHERE id = %s",
            [ids["on"]],
        )
        cr.execute(
            "UPDATE conversation_transport SET smtp_ssl = FALSE WHERE id = %s",
            [ids["off"]],
        )
        self._migrate()
        cr.execute(
            "SELECT id, smtp_encryption FROM conversation_transport WHERE id IN %s",
            [tuple(ids.values())],
        )
        result = dict(cr.fetchall())
        self.assertEqual(result[ids["on"]], "starttls")
        self.assertEqual(result[ids["off"]], "none")
        self.assertEqual(result[ids["null"]], "none")
        # A second run (column present) changes nothing.
        cr.execute(
            "UPDATE conversation_transport SET smtp_encryption = 'ssl' WHERE id = %s",
            [ids["on"]],
        )
        self._migrate()
        cr.execute(
            "SELECT smtp_encryption FROM conversation_transport WHERE id = %s",
            [ids["on"]],
        )
        self.assertEqual(cr.fetchone()[0], "ssl")
