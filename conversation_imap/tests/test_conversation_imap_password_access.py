# Acceptance criteria (conversation_imap, password access):
#   The IMAP ``password`` is administrator-only. A user can still set the
#   password of their OWN personal transport through the write-only
#   ``new_password`` path, but can never read a stored password back.
#   1. Non-admin read of ``password`` on a shared transport raises
#      AccessError (RPC read and attribute access); the field is absent
#      from ``fields_get``.
#   2. Non-admin write of ``password`` raises AccessError, value unchanged.
#   3. Admin reads/writes ``password`` as before.
#   4. Owner sets ``new_password`` on a personal transport: the engine's
#      connection params carry it; nothing can be read back.
#   5. Setting ``new_password`` on another user's personal transport is
#      refused and changes nothing.
#   6. Setting ``new_password`` on a shared transport is refused (also
#      when the same write tries to claim it, and on create).
#   7. The email engine still gets the password for a non-admin working
#      on a shared mailbox.
#   8. The transport form builds for admin and non-admin, and the
#      non-admin form never carries the ``password`` field.
from odoo.exceptions import AccessError
from odoo.tests import Form, HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger


class TestImapPasswordAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.owner = Users.create(
            {
                "name": "Mailbox Owner",
                "login": "mailbox_owner",
                "email": "owner@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.other = Users.create(
            {
                "name": "Other User",
                "login": "other_user",
                "email": "other@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        Transport = cls.env["conversation.transport"]
        vals = {
            "provider": "imap",
            "imap_host": "imap.example.com",
            "smtp_host": "smtp.example.com",
            "login": "box@example.com",
            "password": "shared-secret",
        }
        cls.shared = Transport.create({**vals, "name": "Shared Box"})
        cls.mine = Transport.create(
            {**vals, "name": "Owner Box", "user_id": cls.owner.id, "password": "old"}
        )
        cls.theirs = Transport.create(
            {**vals, "name": "Other Box", "user_id": cls.other.id, "password": "old"}
        )

    def as_owner(self, record):
        return record.with_user(self.owner)

    def stored(self, record):
        return record.sudo().password

    def test_non_admin_cannot_read_shared_password(self):
        shared = self.as_owner(self.shared)
        with self.assertRaises(AccessError):
            shared.read(["password"])
        with self.assertRaises(AccessError):
            self.assertTrue(shared.password)
        self.assertNotIn("password", shared.fields_get())

    def test_non_admin_cannot_write_shared_password(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.as_owner(self.shared).write({"password": "hijacked"})
        self.assertEqual(self.stored(self.shared), "shared-secret")

    def test_admin_reads_and_writes_password(self):
        self.assertEqual(self.shared.password, "shared-secret")
        self.shared.write({"password": "rotated"})
        self.assertEqual(self.shared.read(["password"])[0]["password"], "rotated")

    def test_owner_sets_own_password_without_reading_it_back(self):
        mine = self.as_owner(self.mine)
        mine.write({"new_password": "fresh"})
        self.assertEqual(self.stored(self.mine), "fresh")
        self.assertEqual(mine._email_connection_params()["password"], "fresh")
        self.assertFalse(mine.read(["new_password"])[0]["new_password"])
        self.assertTrue(mine.password_set)
        with self.assertRaises(AccessError):
            mine.read(["password"])

    def test_cannot_set_other_users_personal_password(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.as_owner(self.theirs).write({"new_password": "hijacked"})
        self.assertEqual(self.stored(self.theirs), "old")

    def test_cannot_set_shared_password_through_owner_path(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.as_owner(self.shared).write({"new_password": "hijacked"})
        # Claiming the shared transport in the same write does not help.
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.as_owner(self.shared).write(
                {"user_id": self.owner.id, "new_password": "hijacked"}
            )
        self.assertEqual(self.stored(self.shared), "shared-secret")
        self.assertFalse(self.shared.user_id)

    def test_cannot_create_shared_transport_with_owner_path(self):
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self.env["conversation.transport"].with_user(self.owner).create(
                {"name": "New Shared", "provider": "imap", "new_password": "x"}
            )

    def test_owner_creates_personal_transport_with_password(self):
        created = self.env["conversation.transport"].with_user(self.owner).create(
            {
                "name": "My New Box",
                "provider": "imap",
                "user_id": self.owner.id,
                "new_password": "created",
            }
        )
        self.assertEqual(self.stored(created), "created")

    def test_engine_still_gets_password_on_shared_mailbox(self):
        params = self.as_owner(self.shared)._email_connection_params()
        self.assertEqual(params["password"], "shared-secret")
        self.assertTrue(self.as_owner(self.shared).password_set)

    def test_form_builds_for_admin_and_non_admin(self):
        with Form(self.shared) as form:
            form.password = "from-admin-form"
        self.assertEqual(self.shared.password, "from-admin-form")

        owner_env = self.env(user=self.owner)
        view = owner_env["conversation.transport"].get_view(view_type="form")
        self.assertNotIn('name="password"', view["arch"])
        self.assertIn('name="new_password"', view["arch"])
        with Form(self.as_owner(self.mine)) as form:
            form.new_password = "via-form"
        self.assertEqual(self.stored(self.mine), "via-form")
        # Shared record: the form still builds, and the secret never shows.
        with Form(self.as_owner(self.shared)) as form:
            self.assertTrue(form.password_set)


@tagged("post_install", "-at_install")
class TestImapPasswordOwnerTour(HttpCase):
    def test_owner_sets_own_password(self):
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Tour Owner",
                    "login": "tour_owner",
                    "password": "tour_owner",
                    "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )
        transport = self.env["conversation.transport"].create(
            {
                "name": "Tour Box",
                "provider": "imap",
                "user_id": user.id,
                "login": "tour@example.com",
                "imap_host": "imap.example.com",
                "password": "before",
            }
        )
        self.start_tour(
            f"/odoo/conversation.transport/{transport.id}",
            "imap_password_owner",
            login="tour_owner",
        )
        self.assertEqual(transport.sudo().password, "tour-secret")
