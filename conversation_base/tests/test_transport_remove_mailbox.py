# Acceptance criteria (self-service mailboxes, conversation_base):
#  16. The owner can remove their own mailbox: it is archived, no flag lets
#      Odoo use it any more, and its stored secrets are cleared.
#  17. Removing a mailbox never alters what was filed from it:
#      ``mail.message.transport_id`` / ``external_id`` and
#      ``mail.conversation.primary_transport_id`` keep their values. A
#      transport mail was filed from cannot be hard-deleted (the default
#      ``set null`` would erase those keys); an unused one still can.
#  18. A non-admin cannot list, read, write, remove or create for another
#      user's personal transport, nor remove a shared one (UI and RPC).
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestRemoveMailbox(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        group = cls.env.ref("base.group_user")
        cls.owner = Users.create(
            {
                "name": "Remove Owner",
                "login": "remove_owner",
                "group_ids": [Command.link(group.id)],
            }
        )
        cls.other = Users.create(
            {
                "name": "Remove Other",
                "login": "remove_other",
                "group_ids": [Command.link(group.id)],
            }
        )
        Transport = cls.env["conversation.transport"]
        flags = {"browsable": True, "searchable": True, "sendable": True}
        cls.mine = Transport.create(
            {"name": "Mine", "user_id": cls.owner.id, "login": "me@example.com", **flags}
        )
        cls.theirs = Transport.create(
            {"name": "Theirs", "user_id": cls.other.id, **flags}
        )
        cls.shared = Transport.create({"name": "Shared", **flags})
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Filed from mine", "primary_transport_id": cls.mine.id}
        )
        cls.message = cls.conversation.message_post(body="filed", message_type="comment")
        cls.message.sudo().write({"transport_id": cls.mine.id, "external_id": "42"})

    def test_owner_remove_archives_and_switches_every_capability_off(self):
        self.mine.with_user(self.owner).action_remove_mailbox()
        mine = self.mine.sudo()
        self.assertFalse(mine.active)
        for flag in ("browsable", "searchable", "sendable", "pushable", "mailbox_writable"):
            self.assertFalse(mine[flag], flag)
        # No browse is possible any more.
        with self.assertRaises(UserError):
            self.env["conversation.transport"].browse_page(self.mine.id)

    def test_remove_keeps_filed_mail_and_its_keys(self):
        self.mine.with_user(self.owner).action_remove_mailbox()
        self.assertEqual(self.message.sudo().transport_id, self.mine)
        self.assertEqual(self.message.sudo().external_id, "42")
        self.assertEqual(self.conversation.sudo().primary_transport_id, self.mine)
        self.assertTrue(self.conversation.exists())

    def test_non_admin_cannot_remove_foreign_or_shared_mailbox(self):
        with mute_logger("odoo.models", "odoo.addons.base.models.ir_rule"):
            with self.assertRaises(AccessError):
                self.theirs.with_user(self.owner).action_remove_mailbox()
        with self.assertRaises(AccessError):
            self.shared.with_user(self.owner).action_remove_mailbox()
        self.assertTrue(self.theirs.active and self.shared.active)

    def test_admin_can_remove_a_shared_mailbox(self):
        self.shared.action_remove_mailbox()
        self.assertFalse(self.shared.active)

    def test_transport_with_filed_mail_cannot_be_deleted(self):
        with self.assertRaises(UserError):
            self.mine.sudo().unlink()
        self.assertEqual(self.message.sudo().transport_id, self.mine)

    def test_transport_used_only_as_primary_cannot_be_deleted(self):
        primary_only = self.env["conversation.transport"].create({"name": "Primary"})
        self.env["mail.conversation"].create(
            {"name": "Primary only", "primary_transport_id": primary_only.id}
        )
        with self.assertRaises(UserError):
            primary_only.unlink()

    def test_unused_transport_can_still_be_deleted(self):
        unused = self.env["conversation.transport"].create({"name": "Unused"})
        unused.unlink()
        self.assertFalse(unused.exists())

    def test_another_users_mailbox_is_invisible_and_untouchable(self):
        Transport = self.env["conversation.transport"].with_user(self.owner)
        visible = Transport.search([]).ids
        self.assertIn(self.mine.id, visible)
        self.assertNotIn(self.theirs.id, visible)
        with mute_logger("odoo.models", "odoo.addons.base.models.ir_rule"):
            with self.assertRaises(AccessError):
                self.theirs.with_user(self.owner).read(["name"])
            with self.assertRaises(AccessError):
                self.theirs.with_user(self.owner).write({"name": "Mine now"})

    def test_cannot_create_a_mailbox_for_somebody_else(self):
        with mute_logger("odoo.models", "odoo.addons.base.models.ir_rule"):
            with self.assertRaises(AccessError):
                self.env["conversation.transport"].with_user(self.owner).create(
                    {"name": "Planted", "user_id": self.other.id}
                )

    def test_cannot_take_over_a_shared_mailbox(self):
        with self.assertRaises(AccessError):
            self.shared.with_user(self.owner).write({"user_id": self.owner.id})
