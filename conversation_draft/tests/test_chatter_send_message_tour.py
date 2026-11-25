# Acceptance criteria: on a conversation the chatter shows "Log note" and no
# "Send message" (a real browser tour); a note still posts as an ordinary
# internal note and emails nobody; other models keep "Send message". The same
# holds on a conversation's reply draft (a real browser tour from Reply).

from markupsafe import Markup

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestChatterSendMessageTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_nosend_u", name="Tour User", groups="base.group_user"
        )
        cls.conversation = (
            cls.env["mail.conversation"]
            .with_context(mail_create_nosubscribe=True, mail_create_nolog=True)
            .create({"name": "Chatter button topic"})
        )
        # Soft-launch guard record: a core mail.thread model whose form no other
        # addon extends. A res.partner form is fragile here: other addons add
        # fields a plain internal user cannot read, and the form never renders.
        cls.other_user = mail_new_test_user(
            cls.env,
            login="tour_nosend_sys",
            name="Tour System User",
            groups="base.group_user,base.group_system",
        )
        cls.other_record = cls.env["mail.blacklist"].create(
            {"email": "other-model@example.com"}
        )

    def test_conversation_has_no_send_message(self):
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_no_send_message",
            login=self.user.login,
        )

    def test_other_model_keeps_send_message(self):
        self.start_tour(
            f"/odoo/mail.blacklist/{self.other_record.id}",
            "conversation_send_message_other_model",
            login=self.other_user.login,
        )

    def test_note_on_conversation_sends_no_email(self):
        mails_before = self.env["mail.mail"].search_count([])
        msg = self.conversation.with_user(self.user).message_post(
            body=Markup("<p>Internal only</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.assertEqual(msg.model, "mail.conversation")
        self.assertEqual(msg.subtype_id, self.env.ref("mail.mt_note"))
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)


@tagged("post_install", "-at_install")
class TestDraftChatterSendMessage(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_draft_u", name="Draft Tour User", groups="base.group_user"
        )
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Tour transport", "sendable": True}
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Question de livraison", "primary_transport_id": cls.transport.id}
        )
        cls.env["mail.conversation.participant"].create(
            {
                "conversation_id": cls.conversation.id,
                "email": "client@example.com",
                "role": "requester",
            }
        )

    def test_draft_has_no_send_message(self):
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "draft_no_send_message",
            login=self.user.login,
        )
        draft = self.env["mail.conversation.draft"].search(
            [("conversation_id", "=", self.conversation.id)]
        )
        # The tour really opened the draft from the Reply button.
        self.assertEqual(len(draft), 1)

    def test_note_on_draft_sends_no_email(self):
        draft = self.env["mail.conversation.draft"].browse(
            self.conversation.with_user(self.user).action_open_draft()["res_id"]
        )
        mails_before = self.env["mail.mail"].search_count([])
        msg = draft.with_user(self.user).message_post(
            body=Markup("<p>Internal only</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.assertEqual(msg.model, "mail.conversation.draft")
        self.assertEqual(msg.res_id, draft.id)
        self.assertEqual(msg.subtype_id, self.env.ref("mail.mt_note"))
        self.assertEqual(self.env["mail.mail"].search_count([]), mails_before)
