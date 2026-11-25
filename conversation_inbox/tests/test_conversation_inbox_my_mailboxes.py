# Acceptance criteria (self-service mailboxes, conversation_inbox):
#   1. "My mailboxes" is reachable from the Conversations menu for an
#      internal (non-admin) user, lists their own mailboxes by default.
#   2. A mailbox added from there is created for the current user (the
#      action presets the owner; the form hides it).
#   3. The provider is not preselected: the user picks it explicitly.
#  13. A new mailbox is usable in the Inbox without ticking any flag.
# The IMAP / Gmail specifics (provider fields, tour) are exercised in
# test_conversation_self_service, which has the provider modules installed.
from odoo.fields import Command
from odoo.tests import TransactionCase
from odoo.tools.safe_eval import safe_eval


class TestMyMailboxesAction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Mailbox User",
                    "login": "mailbox_user",
                    "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
                }
            )
        )
        cls.action = cls.env.ref("conversation_inbox.conversation_transport_action_my")

    def _context(self):
        return safe_eval(self.action.context, {"uid": self.user.id})

    def test_menu_is_reachable_by_an_internal_user(self):
        menu = self.env.ref("conversation_inbox.menu_conversation_transport_my")
        visible = self.env["ir.ui.menu"].with_user(self.user)._visible_menu_ids()
        self.assertIn(menu.id, visible)
        self.assertEqual(menu.name, "My mailboxes")

    def test_new_mailbox_defaults_to_the_current_user_and_is_usable(self):
        Transport = self.env["conversation.transport"].with_user(self.user)
        defaults = Transport.with_context(**self._context()).default_get(
            ["user_id", "provider", "browsable", "searchable", "sendable"]
        )
        self.assertEqual(defaults["user_id"], self.user.id)
        self.assertTrue(
            defaults["browsable"] and defaults["searchable"] and defaults["sendable"]
        )
        # The provider is the user's explicit choice, never a load-order accident.
        self.assertFalse(defaults.get("provider"))

    def test_mailbox_created_through_the_action_shows_in_the_inbox_domain(self):
        Transport = self.env["conversation.transport"].with_user(self.user)
        defaults = Transport.with_context(**self._context()).default_get(
            ["user_id", "browsable", "searchable", "sendable"]
        )
        mailbox = Transport.create({"name": "Mine", **defaults})
        listed = Transport.search([("browsable", "=", True)])
        self.assertIn(mailbox, listed)

    def test_self_service_views_build_for_a_non_admin(self):
        Transport = self.env["conversation.transport"].with_user(self.user)
        for view_type in ("list", "form"):
            view = self.action.view_ids.filtered(lambda v: v.view_mode == view_type)
            result = Transport.get_view(view.view_id.id, view_type)
            self.assertIn("action_remove_mailbox", result["arch"])
        form = Transport.get_view(
            self.env.ref("conversation_inbox.conversation_transport_view_form_my").id,
            "form",
        )
        # The owner is fixed and the technical switches are not offered.
        arch = form["arch"]
        self.assertRegex(arch, r'<field name="user_id" readonly="1" force_save="1"')
        for technical in ("browsable", "searchable", "sendable", "pushable"):
            self.assertNotIn(f'<field name="{technical}"/>', arch)
        # Opting in to write-back on one's own mailbox stays available.
        self.assertIn('<field name="mailbox_writable"', arch)
