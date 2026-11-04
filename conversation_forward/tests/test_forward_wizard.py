# Acceptance criteria (AC12/AC14/AC20): the forward wizard is
# prefilled from the conversation / message, takes free-text addresses (any
# address, comma separated) and sends through the conversation's transport.

from unittest.mock import patch

from odoo.tests import Form, tagged

from .common import ForwardCommon


@tagged("post_install", "-at_install")
class TestForwardWizard(ForwardCommon):
    def test_forward_wizard_form_smoke(self):
        form = Form(
            self.env["conversation.forward.wizard"].with_context(
                default_conversation_id=self.conv.id,
                default_message_id=self.m2.id,
            )
        )
        self.assertEqual(form.transport_id, self.transport)
        self.assertEqual(form.forward_mode, "message")
        self.assertEqual(form.subject, "Fwd: Second question")
        self.assertTrue(form.include_attachments)
        self.assertEqual(form.attachment_names, "spec.pdf")

        form.to_emails = "x@example.com, y@example.com"
        wizard = form.save()
        with patch.object(
            type(self.transport), "_send_raw", autospec=True, return_value="<w@x>"
        ) as send:
            action = wizard.action_send()
        self.assertEqual(action["type"], "ir.actions.act_window_close")
        self.assertEqual(
            send.call_args.kwargs["to_emails"], ["x@example.com", "y@example.com"]
        )

        form = Form(
            self.env["conversation.forward.wizard"].with_context(
                default_conversation_id=self.conv.id,
                default_message_id=self.m2.id,
            )
        )
        form.forward_mode = "conversation"
        form.to_emails = "z@example.com"
        wizard = form.save()
        with patch.object(
            type(self.transport), "_send_raw", autospec=True, return_value="<w2@x>"
        ) as send:
            wizard.action_send()
        self.assertEqual(str(send.call_args.kwargs["body"]).count("Forwarded message"), 3)

    def test_forward_wizard_conversation_mode_needs_no_message(self):
        form = Form(
            self.env["conversation.forward.wizard"].with_context(
                default_conversation_id=self.conv.id
            )
        )
        self.assertEqual(form.forward_mode, "conversation")
        form.to_emails = "z@example.com"
        wizard = form.save()
        self.assertFalse(wizard.message_id)
