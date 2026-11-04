# Acceptance criteria: the "Conversations" app root carries its own action
# (the triage list, with the sub-menu's default facets), so the app's landing
# does not depend on which child menu has the lowest sequence.

from odoo.tests import TransactionCase


class TestConversationAppLanding(TransactionCase):
    def test_root_menu_opens_triage_list(self):
        root = self.env.ref("conversation_base.menu_mail_conversation_root")
        action = self.env.ref("conversation_base.mail_conversation_action")
        self.assertEqual(root.action, action)
        entry = self.env["ir.ui.menu"].load_web_menus(False)[root.id]
        self.assertEqual(entry["actionID"], action.id)
        self.assertEqual(entry["actionModel"], "ir.actions.act_window")
        self.assertIn("search_default_filter_my_list", action.context)
        self.assertIn("search_default_filter_open", action.context)
