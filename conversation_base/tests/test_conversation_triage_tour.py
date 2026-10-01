# Acceptance criteria (task #3966, AC15 + AC20):
#   A web_tour drives the Conversations list: handled -> row disappears ->
#   back through the "Handled by me" view -> done -> partial bulk Done ->
#   reopen -> linked-record chip -> keyboard accelerator (j/k, Shift+j,
#   Escape, e, s, editable protection). Dead buttons fail the tour; the
#   end state is then asserted on the server.

from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestConversationTriageTour(HttpCase):
    def test_conversation_triage_tour(self):
        partner = self.env["res.partner"].create({"name": "Tour Partner"})
        outsider = self.env["res.partner"].create(
            {"name": "Tour Customer", "email": "tour.customer@example.com"}
        )
        Conversation = self.env["mail.conversation"].with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True
        )
        now = fields.Datetime.now()
        convs = {}
        # Newest first, so the list order is Alpha, Bravo, ... Foxtrot.
        for index, name in enumerate(
            ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
        ):
            conv = Conversation.create({"name": "Triage %s" % name})
            message = conv.message_post(
                body="Hello from %s" % name,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
                author_id=outsider.id,
            )
            message.date = now - timedelta(hours=index + 1)
            conv._trigger_message_facets()
            convs[name] = conv
        self.env["mail.conversation.link"].create(
            {
                "conversation_id": convs["Charlie"].id,
                "res_model": "res.partner",
                "res_id": partner.id,
            }
        )

        self.start_tour(
            "/odoo",
            "conversation_triage_tour",
            login="admin",
            timeout=180,
        )

        member = self.env["mail.conversation.member"]
        # Alpha: handled then restored, done then reopened -> open, not handled.
        self.assertEqual(convs["Alpha"].state, "open")
        self.assertFalse(
            member.search(
                [("conversation_id", "=", convs["Alpha"].id), ("is_handled", "=", True)]
            )
        )
        # Bravo: done; Charlie: bulk-done and left done.
        self.assertEqual(convs["Bravo"].state, "done")
        self.assertEqual(convs["Charlie"].state, "done")
        self.assertEqual(convs["Delta"].state, "open")
