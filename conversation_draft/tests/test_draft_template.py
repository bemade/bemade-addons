# Acceptance criteria (collaborative shared drafts, templates):
#   * "Use template" on a conversation with no draft creates one seeded with
#     the rendered subject, body and attachments (copied, owned by the draft).
#   * On a draft that already has text, the user chooses to append (both
#     texts kept) or replace (only the template's text).
#   * A template written for another model is refused.

from odoo import Command
from odoo.exceptions import UserError

from .common import DraftCommon


class TestDraftTemplate(DraftCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template_attachment = cls.env["ir.attachment"].create(
            {"name": "terms.txt", "raw": b"terms"}
        )
        cls.template = cls.env["mail.template"].create(
            {
                "name": "Draft template",
                "model_id": cls.env["ir.model"]._get_id("mail.conversation"),
                "subject": "Re: {{ object.name }}",
                "body_html": '<p>Hello about <t t-out="object.name"/></p>',
                "attachment_ids": [Command.link(cls.template_attachment.id)],
            }
        )

    def _apply(self, mode="append", template=None, draft=None):
        wizard = self.env["mail.conversation.draft.template"].with_user(
            self.user_a
        ).create(
            {
                "conversation_id": self.conversation.id,
                "draft_id": draft.id if draft else False,
                "template_id": (template or self.template).id,
                "mode": mode,
            }
        )
        return wizard.action_apply()

    def test_seeds_a_new_draft(self):
        action = self._apply()
        draft = self.Draft.browse(action["res_id"])
        self.assertEqual(draft.subject, "Re: Shared draft topic")
        self.assertIn("Hello about Shared draft topic", draft.body)
        self.assertEqual(len(draft.attachment_ids), 1)
        copy = draft.attachment_ids
        self.assertNotEqual(copy, self.template_attachment)
        self.assertEqual((copy.res_model, copy.res_id), (draft._name, draft.id))

    def test_append_keeps_existing_text(self):
        draft = self._open_draft()
        draft.write({"body": "<p>mine</p>", "subject": "Mine"})
        self._apply("append", draft=draft)
        self.assertIn("mine", draft.body)
        self.assertIn("Hello about", draft.body)
        self.assertEqual(draft.subject, "Mine")

    def test_replace_drops_existing_text(self):
        draft = self._open_draft()
        draft.write({"body": "<p>mine</p>"})
        self._apply("replace", draft=draft)
        self.assertNotIn("mine", draft.body)
        self.assertIn("Hello about", draft.body)

    def test_template_for_another_model_is_refused(self):
        partner_template = self.env["mail.template"].create(
            {
                "name": "Partner template",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "subject": "Hi",
            }
        )
        with self.assertRaises(UserError):
            self._apply(template=partner_template)
