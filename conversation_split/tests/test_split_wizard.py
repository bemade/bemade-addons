# Acceptance criteria (AC4/AC5/AC10/AC20): the split wizard is
# prefilled from the source conversation, lets the user edit the participants
# carried over and drop links, then splits; both entry points (bound server
# action, message action RPC) open it on the right message.

from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval

from .common import SplitCommon


@tagged("post_install", "-at_install")
class TestSplitWizard(SplitCommon):
    def _form(self):
        return Form(
            self.env["conversation.split.wizard"].with_context(
                default_conversation_id=self.conv.id,
                default_message_id=self.m2.id,
            )
        )

    def test_split_wizard_form_smoke(self):
        form = self._form()
        self.assertEqual(form.name, self.m2.subject)
        self.assertEqual(form.user_id, self.user_employee)
        self.assertEqual(len(form.participant_line_ids), 3)
        participants = self.conv.participant_ids
        self.assertEqual(len(form.link_line_ids), 2)

        with form.participant_line_ids.edit(0) as line:
            line.role = "cc"
        form.participant_line_ids.remove(index=1)
        with form.participant_line_ids.new() as line:
            line.email = "bare@example.com"
        form.link_line_ids.remove(index=0)
        wizard = form.save()
        partner_count = self.env["res.partner"].search_count([])

        action = wizard.action_split()

        self.assertEqual(action["res_model"], "mail.conversation")
        new = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(len(new.participant_ids), 3)
        self.assertNotIn(
            participants[1].email_normalized, new.participant_ids.mapped("email_normalized")
        )
        self.assertIn("bare@example.com", new.participant_ids.mapped("email_normalized"))
        self.assertFalse(
            new.participant_ids.filtered(lambda p: p.email == "bare@example.com").partner_id
        )
        edited = new.participant_ids.filtered(
            lambda p: p.email_normalized == participants[0].email_normalized
        )
        self.assertEqual(edited.role, "cc")
        self.assertEqual(len(new.link_ids), 1)
        self.assertEqual(self.env["res.partner"].search_count([]), partner_count)
        self.assertEqual(len(self.conv.link_ids), 2)
        self.assertEqual(len(self.conv.participant_ids), 3)
        self.assertEqual(self.m3.res_id, new.id)

    def test_open_split_wizard_action(self):
        direct = self.conv.action_open_split_wizard(message_id=self.m2.id)
        server_action = self.env.ref("conversation_split.action_conversation_split")
        via_server = server_action.with_context(
            active_model="mail.conversation",
            active_id=self.conv.id,
            active_ids=self.conv.ids,
        ).run()
        for action in (direct, via_server):
            self.assertEqual(action["res_model"], "conversation.split.wizard")
            self.assertEqual(action["target"], "new")
            self.assertEqual(action["context"]["default_conversation_id"], self.conv.id)
        self.assertEqual(direct["context"]["default_message_id"], self.m2.id)

        domain = self.env["conversation.split.wizard"]._fields["message_id"].domain
        allowed = self.env["mail.message"].search(
            safe_eval(domain, {"conversation_id": self.conv.id})
        )
        self.assertIn(self.m2, allowed)
        self.assertNotIn(
            self.customer.message_post(body="x", subtype_xmlid="mail.mt_note"), allowed
        )
