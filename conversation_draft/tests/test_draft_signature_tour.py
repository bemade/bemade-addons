# Acceptance criteria (UI): a user replies from a conversation that has no
# team inbox; the editable reply body already holds their signature (a real
# browser tour); sending adds nothing, so the recorded message carries the
# signature exactly once.

from unittest.mock import patch

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestDraftSignatureTour(HttpCase):
    def test_draft_signature_tour(self):
        user = mail_new_test_user(
            self.env,
            login="tour_sig_u",
            name="Tour Sig User",
            groups="base.group_user",
        )
        user.signature = "<p>Cordialement,<br/>Tour Sig User</p>"
        transport = self.env["conversation.transport"].create(
            {"name": "Tour transport", "sendable": True}
        )
        conversation = self.env["mail.conversation"].create(
            {"name": "Question de livraison", "primary_transport_id": transport.id}
        )
        self.env["mail.conversation.participant"].create(
            {
                "conversation_id": conversation.id,
                "email": "client@example.com",
                "role": "requester",
            }
        )
        with patch.object(
            type(transport), "_send", autospec=True, return_value="ext-tour"
        ):
            self.start_tour(
                "/odoo/action-conversation_base.mail_conversation_action",
                "draft_signature",
                login=user.login,
            )
        self.env.invalidate_all()
        draft = self.env["mail.conversation.draft"].search(
            [("conversation_id", "=", conversation.id)]
        )
        self.assertEqual(draft.state, "sent")
        self.assertEqual(draft.body.count("Tour Sig User"), 1)
        message = conversation.message_ids.filtered("transport_id")
        self.assertEqual(len(message), 1)
        self.assertEqual(message.body.count("Tour Sig User"), 1)
