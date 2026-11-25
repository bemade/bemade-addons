# Acceptance criteria (self-service mailboxes, conversation_imap):
#  11. A non-admin creates an IMAP transport they own with host, port, SSL,
#      SMTP settings, login and a password entered through the write-only
#      ``new_password`` path. The stored ``password`` is never readable by
#      the owner; ``password_set`` says a password is stored.
#  12. Reconnect: the owner can change connection settings and replace the
#      password on their own transport; the owner-only password rules still refuse a
#      password on a shared or foreign transport (covered in
#      test_conversation_imap_password_access).
#  16. Removing the mailbox clears the stored password.
from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestImapSelfService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.owner = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Imap Self Service",
                    "login": "imap_self_service",
                    "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
                }
            )
        )
        cls.vals = {
            "name": "My Imap",
            "provider": "imap",
            "user_id": cls.owner.id,
            "login": "me@example.com",
            "imap_host": "imap.example.com",
            "imap_port": 993,
            "imap_ssl": True,
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "new_password": "s3cret",
            "browsable": True,
            "searchable": True,
            "sendable": True,
        }

    def _create_as_owner(self, **extra):
        return (
            self.env["conversation.transport"]
            .with_user(self.owner)
            .create({**self.vals, **extra})
        )

    def test_owner_adds_imap_mailbox_with_write_only_password(self):
        transport = self._create_as_owner()
        self.assertEqual(transport.user_id, self.owner)
        self.assertTrue(transport.password_set)
        self.assertFalse(transport.new_password)
        self.assertEqual(transport.sudo().password, "s3cret")
        with mute_logger("odoo.fields", "odoo.models"):
            with self.assertRaises(AccessError):
                transport.mapped("password")
        # The engine can still log in with it, server-side.
        self.assertEqual(transport._email_connection_params()["password"], "s3cret")

    def test_owner_reconnect_changes_settings_and_replaces_password(self):
        transport = self._create_as_owner()
        transport.write({"imap_host": "imap2.example.com", "new_password": "newer"})
        self.assertEqual(transport.imap_host, "imap2.example.com")
        self.assertEqual(transport.sudo().password, "newer")
        self.assertTrue(transport.password_set)

    def test_remove_clears_the_stored_password(self):
        transport = self._create_as_owner()
        transport.action_remove_mailbox()
        self.assertFalse(transport.sudo().active)
        self.assertFalse(transport.sudo().password)
        self.assertFalse(transport.sudo().password_set)
        self.assertFalse(transport.sudo().browsable)
