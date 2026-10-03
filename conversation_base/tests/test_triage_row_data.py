# Acceptance criteria (triage list):
#   * The snippet is the plain text of the newest real-activity message,
#     whitespace-collapsed and shortened; tracking noise does not replace it.
#   * The channel is the transport's provider, "internal" without one.
#   * Participants are limited to three, with the rest as a count; a bare
#     email gets initials.
#   * A linked record's name is shown only if the user can read it; a broken
#     link never raises and never leaks a name.

from odoo import Command

from .common_triage import TriageCommon


class TestTriageRowData(TriageCommon):
    def test_snippet_and_channel(self):
        conv = self._inbound(body="<p>Hello <b>world</b></p>")
        conv.user_id = self.internal_user
        self.assertEqual(conv.last_message_snippet, "Hello world")
        long = self._inbound(body="<p>%s</p>" % ("word " * 200))
        self.assertLessEqual(len(long.last_message_snippet), 161)
        self.assertTrue(long.last_message_snippet.endswith("…"))
        empty = self.Conversation.with_context(mail_create_nolog=True).create({"name": "e"})
        self.assertFalse(empty.last_message_snippet)
        self.assertEqual(conv.triage_channel, "internal")
        provider = type(self.transport)._fields["provider"]
        if provider.selection:
            self.transport.provider = provider.selection[0][0]
            conv.invalidate_recordset(["triage_channel"])
            self.assertEqual(conv.triage_channel, self.transport.provider)

    def test_participants_payload(self):
        partners = self.env["res.partner"].create(
            [{"name": "P%s" % i, "email": "p%s@example.com" % i} for i in range(2)]
        )
        conv = self.Conversation.create({"name": "p"})
        Participant = self.env["mail.conversation.participant"]
        for partner in partners:
            Participant.create(
                {"conversation_id": conv.id, "partner_id": partner.id, "email": partner.email}
            )
        for i in range(3):
            Participant.create(
                {"conversation_id": conv.id, "email": "bare%s@example.com" % i}
            )
        payload = conv.with_user(self.internal_user).triage_participants
        self.assertEqual(len(payload["items"]), 3)
        self.assertEqual(payload["extra"], 2)
        bare = Participant.create(
            {"conversation_id": self.Conversation.create({"name": "q"}).id, "email": "jane.doe@example.com"}
        ).conversation_id.triage_participants["items"][0]
        self.assertFalse(bare["partner_id"])
        self.assertEqual(bare["email"], "jane.doe@example.com")
        self.assertEqual(bare["initials"], "JD")

    def test_link_chip_access(self):
        partner = self.env["res.partner"].create({"name": "Linked Co"})
        gone = self.env["res.partner"].create({"name": "Gone Co"})
        param = self.env["ir.config_parameter"].sudo().create(
            {"key": "secret.triage.key", "value": "x"}
        )
        conv = self.Conversation.create({"name": "links"})
        Link = self.env["mail.conversation.link"]
        for model, res_id in (
            ("res.partner", partner.id),
            ("ir.config_parameter", param.id),
            ("res.partner", gone.id),
            ("no.such.model", 1),
        ):
            Link.create({"conversation_id": conv.id, "res_model": model, "res_id": res_id})
        gone.unlink()
        as_a = conv.with_user(self.internal_user)
        payload = as_a.triage_links
        items = {i["res_model"]: i for i in payload["items"]}
        self.assertEqual(len(payload["items"]), 2)
        self.assertEqual(items["res.partner"]["name"], "Linked Co")
        self.assertTrue(items["ir.config_parameter"]["restricted"])
        self.assertFalse(items["ir.config_parameter"]["name"])
        self.assertNotIn("secret.triage.key", str(payload))
        rows = self.Conversation.with_user(self.internal_user).search_read(
            [("id", "=", conv.id)],
            ["name", "triage_links", "triage_participants", "triage_channel",
             "last_message_snippet", "my_unread", "my_hidden", "my_snoozed"],
        )
        self.assertEqual(len(rows), 1)
