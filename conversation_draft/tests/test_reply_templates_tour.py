# Acceptance criteria (reply templates, UI): an administrator creates a
# conversation, sees no template button, creates a reply template from the
# "Reply templates" menu and then finds the template button; the template is
# stored for conversations.

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestReplyTemplatesTour(HttpCase):
    def test_reply_templates_tour(self):
        self.env["mail.template"].search(
            [("model", "=", "mail.conversation")]
        ).unlink()
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "reply_templates",
            login="admin",
        )
        self.env.invalidate_all()
        template = self.env["mail.template"].search(
            [("name", "=", "Accusé de réception")]
        )
        self.assertEqual(len(template), 1)
        self.assertEqual(template.model, "mail.conversation")
        conversation = self.env["mail.conversation"].search(
            [("name", "=", "Question de livraison")]
        )
        self.assertEqual(len(conversation), 1)
        self.assertTrue(conversation.has_reply_templates)
