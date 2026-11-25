# Acceptance criteria (real browser, ordinary internal user):
#   * Open a conversation from the list: the form. "Thread view" shows the
#     messages oldest first with sender, date and content; the internal note is
#     labelled. Reply under a message and at the bottom opens the shared draft
#     in a pop-up over the thread; sending shows the reply at the end of the
#     thread. Forward under a message opens the wizard for that message, at the
#     bottom for the whole conversation. "Form view" returns to the form.
#   * Merely switching views sends nothing and changes no state or member row.

from datetime import timedelta
from unittest.mock import patch

from markupsafe import Markup

from odoo import Command, fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestThreadViewTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_thread_u", name="Tour Thread", groups="base.group_user"
        )
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Thread tour transport", "sendable": True}
        )
        team = cls.env["mail.conversation.team"].create({"name": "Expédition"})
        tag = cls.env["mail.conversation.tag"].create({"name": "Urgent"})
        cls.conversation = cls.env["mail.conversation"].create(
            {
                "name": "Retard de livraison",
                "primary_transport_id": cls.transport.id,
                "user_id": cls.user.id,
                "team_id": team.id,
                "tag_ids": [Command.set(tag.ids)],
            }
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
        now = fields.Datetime.now()
        # The conversation's own creation record is the oldest message.
        cls.conversation.message_ids.write({"date": now - timedelta(days=3)})
        cls.inbound = cls.conversation.message_post(
            body=Markup("<p>Quand ma commande arrive-t-elle ?</p>"),
            subject="Retard de livraison",
            message_type="email",
            subtype_xmlid="mail.mt_note",
            author_id=customer.id,
        )
        cls.inbound.write(
            {
                "external_id": "201",
                "message_id": "<thread-view-inbound@client.example>",
                "date": now - timedelta(days=2),
            }
        )
        cls.note = cls.conversation.message_post(
            body=Markup("<p>Note interne</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        cls.note.write({"date": now - timedelta(days=1)})

    def _snapshot(self):
        self.env.invalidate_all()
        conversation = self.conversation
        return {
            "state": conversation.state,
            "user": conversation.user_id.id,
            # ``unread`` is left out: opening the form already marks it read.
            "members": [
                (m.id, m.is_handled, m.snooze_until) for m in conversation.member_ids
            ],
            "drafts": self.env["mail.conversation.draft"]
            .search([("conversation_id", "=", conversation.id)])
            .ids,
            "messages": self.env["mail.message"]
            .search([("model", "=", conversation._name), ("res_id", "=", conversation.id)])
            .ids,
        }

    def test_thread_view_tour(self):
        before = self._snapshot()
        with patch.object(
            type(self.transport), "_send", autospec=True, return_value="ext-thread"
        ) as sent:
            self.start_tour(
                "/odoo/action-conversation_base.mail_conversation_action",
                "thread_view",
                login=self.user.login,
            )
        self.assertEqual(sent.call_count, 1)
        after = self._snapshot()
        drafts = self.env["mail.conversation.draft"].browse(after["drafts"])
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts.state, "sent")
        self.assertEqual(drafts.conversation_id, self.conversation)
        self.assertIn("votre commande part vendredi", drafts.sent_message_id.body)
        # The reply is the newest message; nothing else changed.
        self.assertEqual(max(after["messages"]), drafts.sent_message_id.id)
        self.assertEqual(after["state"], before["state"])
        self.assertEqual(after["user"], before["user"])
        self.assertEqual(after["members"], before["members"])

    def test_switching_views_writes_nothing(self):
        before = self._snapshot()
        with patch.object(type(self.transport), "_send", autospec=True) as sent:
            self.start_tour(
                "/odoo/action-conversation_base.mail_conversation_action",
                "thread_view_switch_only",
                login=self.user.login,
            )
        self.assertFalse(sent.called)
        self.assertEqual(self._snapshot(), before)
