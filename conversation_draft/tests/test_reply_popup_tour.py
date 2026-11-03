# Acceptance criteria (reply pop-up, real browser, ordinary internal user):
#   * Open a conversation, Reply at the top: the draft opens in a pop-up and
#     the conversation stays behind it. Closing keeps the typed text; Reply
#     again shows it; Send closes the pop-up, leaves the user on the
#     conversation and the message is in the thread. Server state: the draft
#     is sent and its message recorded.
#   * Reply on one received email opens the same draft with that email quoted
#     and recorded as the message being answered.
#   * A received email offers one "Reply", not two.
#   * A colleague who did not start the draft edits it from the Drafts page,
#     in the pop-up.

from unittest.mock import patch

from markupsafe import Markup

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestReplyPopupTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_reply_u", name="Tour Reply", groups="base.group_user"
        )
        cls.colleague = mail_new_test_user(
            cls.env,
            login="tour_reply_c",
            name="Tour Colleague",
            groups="base.group_user",
        )
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Tour transport", "sendable": True}
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Retard de livraison", "primary_transport_id": cls.transport.id}
        )
        cls.env["mail.conversation.participant"].create(
            {
                "conversation_id": cls.conversation.id,
                "email": "client@example.com",
                "role": "requester",
            }
        )
        customer = cls.env["res.partner"].create(
            {"name": "Client Dubois", "email": "client@example.com"}
        )
        cls.inbound = cls.conversation.message_post(
            body=Markup("<p>Quand ma commande arrive-t-elle ?</p>"),
            subject="Retard de livraison",
            subtype_xmlid="mail.mt_note",
            author_id=customer.id,
        )
        cls.inbound.write(
            {"external_id": "101", "message_id": "<tour-inbound@client.example>"}
        )
        cls.conversation.message_post(
            body=Markup("<p>Note interne</p>"), subtype_xmlid="mail.mt_note"
        )

    def _drafts(self):
        self.env.invalidate_all()
        return self.env["mail.conversation.draft"].search(
            [("conversation_id", "=", self.conversation.id)]
        )

    def test_reply_popup_tour(self):
        with patch.object(
            type(self.transport), "_send", autospec=True, return_value="ext-tour"
        ) as sent:
            self.start_tour(
                "/odoo/action-conversation_base.mail_conversation_action",
                "reply_popup",
                login=self.user.login,
            )
        self.assertEqual(sent.call_count, 1)
        sent_draft = self._drafts().filtered(lambda d: d.state == "sent")
        self.assertEqual(len(sent_draft), 1)
        self.assertTrue(sent_draft.sent_message_id)
        self.assertIn("votre commande part vendredi", sent_draft.sent_message_id.body)
        # The per-message Reply at the end of the tour opened a new draft that
        # answers the received email and quotes it.
        pending = self._drafts().filtered(lambda d: d.state == "draft")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending.reply_to_message_id, self.inbound)
        self.assertIn("Quand ma commande arrive-t-elle", pending.body)

    def test_one_reply_per_message(self):
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "reply_popup_actions",
            login=self.user.login,
        )

    def test_colleague_edits_from_the_drafts_page(self):
        draft = self.env["mail.conversation.draft"]._get_or_create_for(
            self.conversation
        )
        draft.with_user(self.user).write({"body": "<p>Début par un collègue</p>"})
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "reply_popup_drafts_page",
            login=self.colleague.login,
        )
        draft = self._drafts()
        self.assertEqual(draft.subject, "Rédigé par un collègue")
        self.assertIn("Début par un collègue", draft.body)
        self.assertEqual(draft.state, "draft")
