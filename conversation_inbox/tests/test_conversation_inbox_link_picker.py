# Acceptance criteria: in the capture dialog's "Link to a Record" mode the
# record is chosen from a searchable many2one-style picker bound to the
# chosen model, not typed as a database id.
#   - changing the model clears the picked record;
#   - capturing with a model and a picked record links exactly that record;
#   - capturing without a record raises and creates nothing;
#   - a header-resolved record is preselected and survives the form load;
#   - all of it works for a plain internal user (no access to ir.model);
#   - a record the user cannot read is never offered nor linked.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import Form, TransactionCase
from odoo.tools.misc import mute_logger

from .test_conversation_inbox_wizards import InboxWizardTestMixin


class TestConversationInboxLinkPicker(InboxWizardTestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {
                "name": "Picker User",
                "login": "picker_user@example.com",
                "email": "picker_user@example.com",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )
        cls.transport.write({"user_id": cls.user.id, "record_link_mode": "suggest"})
        cls.partner = cls.env["res.partner"].create({"name": "Picker Partner"})
        cls.other = cls.env["res.partner"].create({"name": "Picker Other"})

    def _form(self, **context):
        context.setdefault("default_transport_id", self.transport.id)
        context.setdefault("default_external_id", "ext-picker")
        context.setdefault("default_mode", "link")
        return Form(
            self.env["conversation.inbox.capture.wizard"]
            .with_user(self.user)
            .with_context(**context)
        )

    def _counts(self):
        return tuple(
            self.env[m].search_count([])
            for m in ("mail.conversation", "mail.conversation.link", "mail.message")
        )

    def test_plain_user_links_the_picked_record(self):
        form = self._form()
        form.res_model = "res.partner"
        form.res_id = self.partner.id
        wizard = form.save()
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            external_id="ext-picker"
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_capture()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(
            [(l.res_model, l.res_id) for l in conversation.link_ids],
            [("res.partner", self.partner.id)],
        )

    def test_changing_the_model_clears_the_record(self):
        form = self._form()
        form.res_model = "res.partner"
        form.res_id = self.partner.id
        form.res_model = "mail.conversation"
        self.assertFalse(form.res_id)

    def test_capture_without_record_creates_nothing(self):
        form = self._form()
        form.res_model = "res.partner"
        wizard = form.save()
        before = self._counts()
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            external_id="ext-picker"
        )
        with fetch_patch, normalize_patch, mute_logger("odoo.sql_db"):
            with self.assertRaisesRegex(UserError, "Pick a record"):
                wizard.action_capture()
        self.assertEqual(self._counts(), before)

    def test_preselected_record_survives_form_load(self):
        form = self._form(default_res_model="res.partner", default_res_id=self.partner.id)
        self.assertEqual(form.res_model, "res.partner")
        self.assertEqual(form.res_id, self.partner.id)

    def test_model_choices_are_readable_business_models_only(self):
        choices = dict(
            self.env["conversation.inbox.capture.wizard"]
            .with_user(self.user)
            ._selection_res_model()
        )
        self.assertIn("res.partner", choices)
        self.assertNotIn("conversation.inbox.capture.wizard", choices)

    def test_unreadable_record_is_not_linked(self):
        company_b = self.env["res.company"].create({"name": "Company B picker"})
        self.partner.sudo().company_id = company_b
        wizard = (
            self.env["conversation.inbox.capture.wizard"]
            .with_user(self.user)
            .create(
                {
                    "transport_id": self.transport.id,
                    "external_id": "ext-picker",
                    "mode": "link",
                    "res_model": "res.partner",
                    "res_id": self.partner.id,
                }
            )
        )
        self.assertFalse(wizard.res_display_name)
        with self.assertRaisesRegex(UserError, "could not be found"):
            wizard._get_link_target()
