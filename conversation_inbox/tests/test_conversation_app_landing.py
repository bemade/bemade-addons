# Acceptance criteria:
#   - With conversation_inbox installed, the "Conversations" app resolves
#     (ir.ui.menu.load_web_menus) to conversation_base.mail_conversation_action,
#     not to the Inbox client action.
#   - That holds whatever child menus exist: a new child with a lower sequence
#     than the Conversations sub-menu must not take the landing over again.
#   - The Inbox menu stays under the app root and still opens the inbox client
#     action; the app's sub-menu entries and their order are unchanged.
#   - A browser tour clicking the app from the main menu lands on the list
#     (with the sub-menu's default facets) and can still reach the Inbox.

from odoo.tests import HttpCase, TransactionCase, tagged


class TestConversationAppLanding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = cls.env.ref("conversation_base.menu_mail_conversation_root")
        cls.list_action = cls.env.ref("conversation_base.mail_conversation_action")
        cls.inbox_action = cls.env.ref(
            "conversation_inbox.conversation_inbox_client_action"
        )

    def _app_entry(self):
        return self.env["ir.ui.menu"].load_web_menus(False)[self.root.id]

    def test_app_opens_conversation_list(self):
        entry = self._app_entry()
        self.assertEqual(entry["actionModel"], "ir.actions.act_window")
        self.assertEqual(entry["actionID"], self.list_action.id)

    def test_landing_independent_of_child_sequence(self):
        self.env["ir.ui.menu"].create(
            {
                "name": "Early Child",
                "parent_id": self.root.id,
                "sequence": 1,
                "action": "ir.actions.client,%d" % self.inbox_action.id,
            }
        )
        self.assertEqual(self._app_entry()["actionID"], self.list_action.id)

    def test_inbox_menu_unchanged(self):
        inbox = self.env.ref("conversation_inbox.menu_conversation_inbox")
        self.assertEqual(inbox.parent_id, self.root)
        self.assertEqual(inbox.name, "Inbox")
        self.assertEqual(inbox.action, self.inbox_action)

    def test_submenu_bar_order_unchanged(self):
        names = self.root.child_id.sorted("sequence").mapped("name")
        # Other conversation_* modules may add entries; the known ones keep
        # their relative order.
        known = ("Inbox", "Conversations", "Teams", "My mailboxes")
        self.assertEqual([n for n in names if n in known], list(known))


@tagged("post_install", "-at_install")
class TestConversationAppLandingTour(HttpCase):
    def test_app_landing_tour(self):
        # Start inside another app: with web_enterprise, /odoo shows the home
        # menu rather than an app with a navbar.
        self.start_tour(
            "/odoo/discuss", "conversation_app_landing_tour", login="admin"
        )
