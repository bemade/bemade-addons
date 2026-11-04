# Mailbox permissions on shared (ownerless) conversation transports.
#   - archive / mark read stay open to any internal user;
#   - trash_item on a shared transport needs "Delete shared mail", over RPC
#     entry points too, and never reaches the provider hook without it;
#   - personal transports are unchanged (owner decides);
#   - a shared transport can only end up mailbox_writable through a
#     Conversations manager, by create, write or clearing the owner.
# Every actor is a plain user created here, never the superuser.

from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

HOOKS = ("_archive_remote", "_trash_remote", "_mark_read_remote")


def _make_user(env, login, *xmlids):
    groups = ["base.group_user", *xmlids]
    return env["res.users"].create(
        {
            "name": login,
            "login": login,
            "email": "%s@example.com" % login,
            "group_ids": [Command.set([env.ref(x).id for x in groups])],
        }
    )


@tagged("post_install", "-at_install")
class TestTransportPermissions(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Transport = cls.env["conversation.transport"]
        cls.member = _make_user(cls.env, "conv_perm_member")
        cls.deleter = _make_user(
            cls.env, "conv_perm_deleter", "conversation_base.group_delete_shared_mail"
        )
        cls.manager = _make_user(
            cls.env, "conv_perm_manager", "conversation_base.group_conversation_manager"
        )
        cls.admin_user = _make_user(cls.env, "conv_perm_admin", "base.group_system")
        cls.shared = Transport.create(
            {
                "name": "Shared Mailbox",
                "browsable": True,
                "mailbox_writable": True,
                "user_id": False,
            }
        )
        cls.personal = Transport.create(
            {
                "name": "Personal Mailbox",
                "browsable": True,
                "mailbox_writable": True,
                "user_id": cls.member.id,
            }
        )
        cls.calls = []
        for hook in HOOKS:
            cls._patch_hook(cls, hook)

    def _patch_hook(self, hook):
        def fake(transport, external_id):
            self.calls.append((hook, transport.id, external_id))
            return True

        patcher = patch.object(
            type(self.env["conversation.transport"]), hook, fake, create=True
        )
        patcher.start()
        self.addClassCleanup(patcher.stop)

    def setUp(self):
        super().setUp()
        self.calls.clear()

    def _rpc(self, user, method, transport):
        return getattr(self.env["conversation.transport"].with_user(user), method)(
            transport.id, "ext-1"
        )

    # -- groups ----------------------------------------------------

    def test_groups_are_independent_and_admin_holds_both(self):
        manager = self.env.ref("conversation_base.group_conversation_manager")
        delete = self.env.ref("conversation_base.group_delete_shared_mail")
        self.assertFalse(self.env.ref("base.group_user").all_implied_ids & manager)
        self.assertFalse(self.env.ref("base.group_user").all_implied_ids & delete)
        self.assertNotIn(delete, manager.all_implied_ids)
        self.assertFalse(self.manager.has_group("conversation_base.group_delete_shared_mail"))
        self.assertTrue(self.admin_user.has_group("conversation_base.group_conversation_manager"))
        self.assertTrue(self.admin_user.has_group("conversation_base.group_delete_shared_mail"))

    # -- archive / mark read stay member actions -------------------

    def test_member_can_archive_and_mark_read_on_shared(self):
        self._rpc(self.member, "archive_item", self.shared)
        self._rpc(self.member, "mark_read_item", self.shared)
        self.assertEqual(
            [c[0] for c in self.calls], ["_archive_remote", "_mark_read_remote"]
        )

    def test_writable_gate_still_applies_to_shared(self):
        self.shared.write({"mailbox_writable": False})
        with self.assertRaises(UserError):
            self._rpc(self.member, "archive_item", self.shared)
        self.assertFalse(self.calls)

    # -- delete on shared needs the delete group -------------------

    def test_member_cannot_trash_on_shared(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(AccessError):
            self._rpc(self.member, "trash_item", self.shared)
        self.assertFalse(self.calls)

    def test_manager_alone_cannot_trash_on_shared(self):
        with self.assertRaises(AccessError):
            self._rpc(self.manager, "trash_item", self.shared)
        self.assertFalse(self.calls)

    def test_member_cannot_trash_over_jsonrpc_dispatch(self):
        # The same entry point the web client reaches via orm.call.
        from odoo.service.model import call_kw

        with self.assertRaises(AccessError):
            call_kw(
                self.env["conversation.transport"].with_user(self.member),
                "trash_item",
                [self.shared.id, "ext-1"],
                {},
            )
        self.assertFalse(self.calls)

    def test_deleter_can_trash_on_shared(self):
        self._rpc(self.deleter, "trash_item", self.shared)
        self.assertEqual(self.calls, [("_trash_remote", self.shared.id, "ext-1")])

    def test_admin_can_trash_on_shared(self):
        self._rpc(self.admin_user, "trash_item", self.shared)
        self.assertEqual(self.calls, [("_trash_remote", self.shared.id, "ext-1")])

    def test_can_trash_mail_flag_mirrors_the_check(self):
        flag = lambda user, rec: rec.with_user(user).can_trash_mail  # noqa: E731
        self.assertFalse(flag(self.member, self.shared))
        self.assertTrue(flag(self.deleter, self.shared))
        self.assertTrue(flag(self.member, self.personal))

    # -- personal transports unchanged -----------------------------

    def test_owner_has_all_three_actions_on_personal(self):
        for method in ("archive_item", "mark_read_item", "trash_item"):
            self._rpc(self.member, method, self.personal)
        self.assertEqual(
            [c[0] for c in self.calls],
            ["_archive_remote", "_mark_read_remote", "_trash_remote"],
        )

    def test_unimplemented_hook_is_still_a_clear_user_error(self):
        bare = self.env["conversation.transport"].create(
            {"name": "Bare", "browsable": True, "mailbox_writable": True,
             "user_id": self.member.id}
        )
        cls = type(bare)
        with patch.object(cls, "_archive_remote", side_effect=NotImplementedError,
                          autospec=True):
            with self.assertRaises(UserError):
                bare.with_user(self.member).archive_item(bare.id, "x")

    # -- enabling write-back on a shared transport: managers only --

    def test_non_manager_cannot_create_shared_writable(self):
        Transport = self.env["conversation.transport"].with_user(self.member)
        with self.assertRaises(AccessError):
            Transport.create({"name": "Sneaky", "mailbox_writable": True})
        self.assertFalse(
            self.env["conversation.transport"].search([("name", "=", "Sneaky")])
        )

    def test_non_manager_cannot_enable_writable_on_shared(self):
        shared = self.env["conversation.transport"].create({"name": "Shared Off"})
        with self.assertRaises(AccessError):
            shared.with_user(self.member).write({"mailbox_writable": True})
        self.assertFalse(shared.mailbox_writable)

    def test_non_manager_cannot_orphan_a_writable_personal_transport(self):
        with self.assertRaises(AccessError):
            self.personal.with_user(self.member).write({"user_id": False})
        self.assertEqual(self.personal.user_id, self.member)

    def test_non_manager_cannot_orphan_and_enable_in_one_write(self):
        mine = self.env["conversation.transport"].create(
            {"name": "Mine", "user_id": self.member.id}
        )
        with self.assertRaises(AccessError):
            mine.with_user(self.member).write(
                {"user_id": False, "mailbox_writable": True}
            )
        self.assertEqual(mine.user_id, self.member)
        self.assertFalse(mine.mailbox_writable)

    def test_manager_can_do_all_three(self):
        Transport = self.env["conversation.transport"].with_user(self.manager)
        created = Transport.create({"name": "Mgr Shared", "mailbox_writable": True})
        self.assertTrue(created.mailbox_writable)
        shared = Transport.create({"name": "Mgr Shared Off"})
        shared.write({"mailbox_writable": True})
        self.assertTrue(shared.mailbox_writable)
        personal = Transport.create(
            {"name": "Mgr Personal", "user_id": self.manager.id,
             "mailbox_writable": True}
        )
        personal.write({"user_id": False})
        self.assertFalse(personal.user_id)

    def test_owner_controls_write_back_on_personal(self):
        Transport = self.env["conversation.transport"].with_user(self.member)
        mine = Transport.create(
            {"name": "Own", "user_id": self.member.id, "mailbox_writable": True}
        )
        self.assertTrue(mine.mailbox_writable)
        mine.write({"mailbox_writable": False})
        mine.write({"mailbox_writable": True})
        self.assertTrue(mine.mailbox_writable)

    def test_non_manager_can_edit_other_fields_and_switch_off(self):
        # Existing writable shared accounts stay as they are; editing other
        # fields or switching write-back off is not restricted.
        shared = self.shared.with_user(self.member)
        shared.write({"login": "desk@example.com", "mailbox_writable": True})
        shared.write({"mailbox_writable": False})
        self.assertFalse(self.shared.mailbox_writable)

    def test_non_manager_cannot_take_ownership_of_writable_shared(self):
        # Ownership takeover: becoming the owner would make the shared
        # account personal and hand the member delete rights.
        with self.assertRaises(AccessError):
            self.shared.with_user(self.member).write({"user_id": self.member.id})
        self.assertFalse(self.shared.user_id)
        self.assertTrue(self.shared.mailbox_writable)
        with self.assertRaises(AccessError):
            self._rpc(self.member, "trash_item", self.shared)
        self.assertFalse(self.calls)

    def test_non_manager_cannot_take_ownership_and_enable_in_one_write(self):
        shared = self.env["conversation.transport"].create({"name": "Shared Off 2"})
        with self.assertRaises(AccessError):
            shared.with_user(self.member).write(
                {"user_id": self.member.id, "mailbox_writable": True}
            )
        self.assertFalse(shared.user_id)
        self.assertFalse(shared.mailbox_writable)

    def test_non_manager_cannot_claim_a_non_writable_shared(self):
        # Claiming any shared account is refused, whatever its write-back
        # state: otherwise claim-then-enable would reach the same takeover.
        shared = self.env["conversation.transport"].create({"name": "Shared Off 3"})
        with self.assertRaises(AccessError):
            shared.with_user(self.member).write({"user_id": self.member.id})
        self.assertFalse(shared.user_id)

    def test_shared_to_personal_needs_a_manager(self):
        # Two-step path: the member cannot claim the account; once a manager
        # has made it personal, the owner decides about write-back.
        shared = self.env["conversation.transport"].create({"name": "Shared Off 4"})
        with self.assertRaises(AccessError):
            shared.with_user(self.member).write({"user_id": self.member.id})
        with self.assertRaises(AccessError):
            shared.with_user(self.member).write({"mailbox_writable": True})
        self.assertFalse(shared.user_id)
        self.assertFalse(shared.mailbox_writable)
        shared.with_user(self.manager).write({"user_id": self.member.id})
        shared.with_user(self.member).write({"mailbox_writable": True})
        self.assertTrue(shared.mailbox_writable)

    def test_manager_can_assign_owner_to_writable_shared(self):
        shared = self.env["conversation.transport"].create(
            {"name": "Shared On", "mailbox_writable": True}
        )
        shared.with_user(self.manager).write({"user_id": self.member.id})
        self.assertEqual(shared.user_id, self.member)

    def test_non_manager_can_reassign_a_personal_transport(self):
        # Only SHARED accounts are protected from takeover; personal
        # accounts keep their owner-decides behaviour.
        self.personal.with_user(self.member).write({"user_id": self.deleter.id})
        self.assertEqual(self.personal.user_id, self.deleter)
