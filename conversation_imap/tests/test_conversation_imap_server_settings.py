# Acceptance criteria (conversation_imap, shared account server settings):
#   1. A plain internal user cannot change the server, port, encryption,
#      login or provider of a shared account (ORM write and RPC-like write).
#   2. Giving the account an owner in the same write does not get around it.
#   3. A Conversations manager and an administrator can change them.
#   4. The owner changes them on their own account.
#   5. Other fields of a shared account stay writable as before.
#   6. A non-manager cannot create a shared account with server settings.
#   7. The form still opens for an ordinary user.
from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import Form, HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger

CHANGES = {
    "login": "other@example.com",
    "imap_host": "evil.example.com",
    "imap_port": 143,
    "imap_ssl": False,
    "smtp_host": "evil.example.com",
    "smtp_port": 25,
    "smtp_encryption": "none",
    "smtp_ssl": False,
}


class TestImapServerSettings(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        user_group = cls.env.ref("base.group_user")

        def make(login, *groups):
            return Users.create(
                {
                    "name": login,
                    "login": login,
                    "email": f"{login}@example.com",
                    "group_ids": [Command.set([user_group.id, *[g.id for g in groups]])],
                }
            )

        cls.plain = make("settings_plain")
        cls.manager = make(
            "settings_manager",
            cls.env.ref("conversation_base.group_conversation_manager"),
        )
        cls.admin = make("settings_admin", cls.env.ref("base.group_system"))
        cls.shared = cls.env["conversation.transport"].create(
            {
                "name": "Shared Box",
                "provider": "imap",
                "login": "box@example.com",
                "imap_host": "imap.example.com",
                "smtp_host": "smtp.example.com",
                "password": "shared-secret",
            }
        )
        cls.mine = cls.env["conversation.transport"].create(
            {
                "name": "Plain Box",
                "provider": "imap",
                "user_id": cls.plain.id,
                "login": "me@example.com",
                "imap_host": "imap.example.com",
                "smtp_host": "smtp.example.com",
                "password": "mine",
            }
        )

    def as_user(self, record, user):
        return record.with_user(user)

    def test_plain_user_cannot_change_shared_settings(self):
        shared = self.as_user(self.shared, self.plain)
        for field, value in CHANGES.items():
            with self.subTest(field=field), mute_logger("odoo.models"):
                with self.assertRaises(AccessError):
                    shared.write({field: value})
        with self.assertRaises(AccessError):
            shared.write({"provider": False})
        with self.assertRaises(AccessError):
            shared.write(dict(CHANGES))
        self.shared.invalidate_recordset()
        self.assertEqual(self.shared.imap_host, "imap.example.com")
        self.assertEqual(self.shared.login, "box@example.com")
        self.assertEqual(self.shared.smtp_encryption, "starttls")
        self.assertEqual(self.shared.sudo().password, "shared-secret")

    def test_plain_user_cannot_change_settings_over_rpc(self):
        shared = self.as_user(self.shared, self.plain)
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            shared.web_save({"imap_host": "evil.example.com"}, {"id": {}})
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            shared.web_save({"smtp_ssl": False}, {"id": {}})
        self.assertEqual(self.shared.imap_host, "imap.example.com")

    def test_claiming_the_account_does_not_help(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.as_user(self.shared, self.plain).write(
                {"user_id": self.plain.id, "imap_host": "evil.example.com"}
            )
        self.assertFalse(self.shared.user_id)
        self.assertEqual(self.shared.imap_host, "imap.example.com")

    def test_manager_and_admin_change_shared_settings(self):
        self.as_user(self.shared, self.manager).write(
            {"imap_host": "imap.manager.example.com", "smtp_encryption": "ssl"}
        )
        self.assertEqual(self.shared.imap_host, "imap.manager.example.com")
        self.assertEqual(self.shared.smtp_encryption, "ssl")
        self.as_user(self.shared, self.admin).write(dict(CHANGES))
        self.assertEqual(self.shared.login, "other@example.com")
        self.assertEqual(self.shared.smtp_port, 25)

    def test_owner_changes_own_settings(self):
        self.as_user(self.mine, self.plain).write(dict(CHANGES))
        self.assertEqual(self.mine.imap_host, "evil.example.com")
        self.assertEqual(self.mine.login, "other@example.com")
        self.assertEqual(self.mine.smtp_encryption, "none")

    def test_other_fields_of_shared_account_stay_writable(self):
        shared = self.as_user(self.shared, self.plain)
        shared.write({"name": "Renamed", "imap_host": "imap.example.com"})
        self.assertEqual(self.shared.name, "Renamed")

    def test_plain_user_cannot_create_shared_account_with_server(self):
        Transport = self.env["conversation.transport"].with_user(self.plain)
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            Transport.create(
                {"name": "New Shared", "provider": "imap", "imap_host": "x.example.com"}
            )
        # Defaults sent by a form are not a change; a personal account is fine.
        Transport.create({"name": "Defaults", "provider": "imap", "imap_port": 993})
        created = Transport.create(
            {
                "name": "Personal",
                "provider": "imap",
                "user_id": self.plain.id,
                "imap_host": "imap.example.com",
            }
        )
        self.assertEqual(created.imap_host, "imap.example.com")

    def test_form_opens_for_plain_user_on_shared_account(self):
        with Form(self.as_user(self.shared, self.plain)) as form:
            self.assertEqual(form.imap_host, "imap.example.com")
            form.name = "Renamed in form"
        self.assertEqual(self.shared.name, "Renamed in form")


@tagged("post_install", "-at_install")
class TestImapSharedSettingsTour(HttpCase):
    def test_plain_user_is_refused_on_shared_account(self):
        self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "Tour Plain",
                "login": "tour_plain",
                "password": "tour_plain",
                "group_ids": [Command.link(self.env.ref("base.group_user").id)],
            }
        )
        transport = self.env["conversation.transport"].create(
            {
                "name": "Tour Shared Box",
                "provider": "imap",
                "login": "tour@example.com",
                "imap_host": "imap.example.com",
            }
        )
        self.start_tour(
            f"/odoo/conversation.transport/{transport.id}",
            "imap_shared_settings_locked",
            login="tour_plain",
        )
        transport.invalidate_recordset()
        self.assertEqual(transport.imap_host, "imap.example.com")
