# Acceptance criteria (the reply window stays fast to open and save):
#   * Reading ``attachment_ids`` on a reply wizard, or computing its field
#     description / view / group-by join, never runs an access-checked
#     search over every record-linked attachment in the database (that scan
#     costs seconds on a large database, even for a wizard with no files).
#   * Attachment visibility is unchanged: the list is the same for an
#     administrator and a non-admin internal user, and the wizard form
#     still loads and saves for the latter with a file added.

import base64
from unittest.mock import patch

from odoo import Command
from odoo.tests import Form, TransactionCase

from .test_conversation_inbox_wizards import InboxWizardTestMixin


class TestReplyWizardAttachmentAccess(InboxWizardTestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A shared mailbox, so a plain internal user may open the window.
        cls.transport.user_id = False
        cls.user = cls.env["res.users"].create(
            {
                "name": "Reply Window User",
                "login": "reply_window_user",
                "email": "reply_window_user@example.com",
                "group_ids": [Command.set([cls.env.ref("base.group_user").id])],
            }
        )

    def _attachment(self, name):
        # Created by the user, as the many2many_binary widget does.
        return self.env["ir.attachment"].with_user(self.user).create(
            {
                "name": name,
                "datas": base64.b64encode(b"x"),
                "res_model": "conversation.inbox.reply.wizard",
                "res_id": 0,
            }
        )

    def _wizard(self, *attachments):
        context = {
            "default_transport_id": self.transport.id,
            "default_external_id": "ext-aa",
            "default_action_type": "reply",
        }
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-aa")
        with fetch_patch, normalize_patch:
            return (
                self.env["conversation.inbox.reply.wizard"]
                .with_user(self.user)
                .with_context(**context)
                .create(
                    {
                        "body": "<p>Hi</p>",
                        "attachment_ids": [Command.set([a.id for a in attachments])],
                    }
                )
            )

    def _record_attachment_searches(self):
        """Patch ``ir.attachment._search`` and collect the ``bypass_access``
        flag of every call, so a test can tell an access-checked scan from a
        join that skips the (expensive, unnarrowed) access filter."""
        calls = []
        model = type(self.env["ir.attachment"])
        original = model._search

        def recording(this, domain, *args, **kwargs):
            calls.append(bool(kwargs.get("bypass_access")))
            return original(this, domain, *args, **kwargs)

        return calls, patch.object(model, "_search", recording)

    def test_reading_attachments_skips_the_access_scan(self):
        att1, att2 = self._attachment("a.txt"), self._attachment("b.txt")
        wizard = self._wizard(att1, att2)
        wizard.invalidate_recordset()
        calls, patcher = self._record_attachment_searches()
        with patcher:
            names = sorted(wizard.attachment_ids.mapped("name"))
        self.assertEqual(names, ["a.txt", "b.txt"])
        self.assertTrue(calls, "the field read should query attachments")
        self.assertTrue(all(calls), "attachment_ids must not run an access-checked scan")

    def test_field_description_view_and_group_by_skip_the_access_scan(self):
        wizard = self._wizard()
        calls, patcher = self._record_attachment_searches()
        with patcher:
            wizard.fields_get(["attachment_ids"])
            wizard.get_views([(False, "form")])
            wizard._read_group_groupby(
                wizard._table, "attachment_ids", wizard._search([])
            )
        self.assertTrue(calls, "the field description should query attachments")
        self.assertTrue(all(calls), "attachment_ids must not run an access-checked scan")

    def test_attachment_list_is_the_same_for_admin_and_internal_user(self):
        att1, att2 = self._attachment("one.txt"), self._attachment("two.txt")
        wizard = self._wizard(att1, att2)
        self.env.invalidate_all()
        as_admin = wizard.with_user(self.env.ref("base.user_admin"))
        as_user = wizard.with_user(self.user)
        self.assertCountEqual(as_admin.attachment_ids.ids, (att1 | att2).ids)
        self.assertCountEqual(as_user.attachment_ids.ids, (att1 | att2).ids)

    def test_form_loads_and_saves_for_internal_user_with_a_file(self):
        context = {
            "default_transport_id": self.transport.id,
            "default_external_id": "ext-aa",
            "default_action_type": "reply",
        }
        attachment = self._attachment("added.txt")
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-aa")
        with fetch_patch, normalize_patch:
            model = self.env["conversation.inbox.reply.wizard"].with_user(self.user)
            with Form(model.with_context(**context)) as form:
                form.body = "<p>Thanks</p>"
                form.attachment_ids.add(attachment)
            wizard = form.record
        self.assertEqual(wizard.attachment_ids, attachment)
        self.assertEqual(wizard.body, "<p>Thanks</p>")
