# Acceptance criteria: a reply sent on a conversation and delivered shows no
# delivery-failure envelope in the conversation, although the other internal
# members received an in-app notification for it. A browser tour drives the
# real conversation form; the server side proves the premise (a notification
# exists, none of them failed) and that nothing was routed through email.

from unittest.mock import patch

from markupsafe import Markup

from odoo import Command
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestConversationDeliveryIconTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_icon_u", name="Tour Sender", groups="base.group_user"
        )
        cls.colleague = mail_new_test_user(
            cls.env,
            login="tour_icon_b",
            name="Tour Colleague",
            groups="base.group_user",
        )
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Fake Mailbox", "provider": False, "sendable": True}
        )
        team = cls.env["mail.conversation.team"].create(
            {
                "name": "Icon Team",
                "member_ids": [Command.set([cls.user.id, cls.colleague.id])],
            }
        )
        cls.conversation = (
            cls.env["mail.conversation"]
            .with_context(mail_create_nosubscribe=True, mail_create_nolog=True)
            .create(
                {
                    "name": "Livraison de commande",
                    "team_id": team.id,
                    "primary_transport_id": cls.transport.id,
                }
            )
        )
        # A colleague following the conversation is what gets the in-app
        # notification that makes stock Odoo draw the delivery icon.
        cls.conversation.message_subscribe(partner_ids=cls.colleague.partner_id.ids)

    def test_delivered_reply_shows_no_failure_icon(self):
        transport_cls = type(self.transport)
        with patch.object(
            transport_cls, "_send", return_value="<delivered@example.com>"
        ) as send:
            message = self.conversation.with_user(self.user).action_reply(
                Markup("<p>Votre commande part demain</p>"),
                recipients=["client@example.com"],
            )
        send.assert_called_once()
        notifications = message.sudo().notification_ids
        # The premise: the colleague was notified in-app, nothing failed,
        # and nothing was emailed through Odoo's pipeline.
        self.assertTrue(notifications)
        self.assertFalse(
            notifications.filtered(
                lambda n: n.notification_status in ("exception", "bounce")
            )
        )
        self.assertFalse(notifications.filtered(lambda n: n.notification_type == "email"))
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_delivery_icon_tour",
            login=self.user.login,
        )
