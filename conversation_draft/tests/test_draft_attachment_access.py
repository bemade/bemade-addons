# Acceptance criteria (draft attachments stay cheap to read):
#   * Reading ``attachment_ids`` on a draft, or computing its field
#     description / group-by join, never runs an access-checked search over
#     every record-linked attachment in the database (that scan costs seconds
#     on a database with hundreds of thousands of attachments, even when the
#     draft has none).
#   * Attachment visibility and behaviour are unchanged: the list is the same
#     for an administrator and a non-admin internal user, and it stays
#     read-only once the draft is no longer a draft.

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form

from .common import DraftCommon


class TestDraftAttachmentAccess(DraftCommon):
    def _attach(self, draft, name):
        attachment = self.env["ir.attachment"].create(
            {"name": name, "raw": b"x", "res_model": draft._name, "res_id": draft.id}
        )
        draft.write({"attachment_ids": [Command.link(attachment.id)]})
        return attachment

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
        draft = self._open_draft(self.user_a)
        self._attach(draft, "a.txt")
        draft.invalidate_recordset()
        as_user = draft.with_user(self.user_b)
        calls, patcher = self._record_attachment_searches()
        with patcher:
            names = as_user.attachment_ids.mapped("name")
        self.assertEqual(names, ["a.txt"])
        self.assertTrue(calls, "the field read should query attachments")
        self.assertTrue(
            all(calls), "attachment_ids must not run an access-checked scan"
        )

    def test_field_description_and_group_by_skip_the_access_scan(self):
        draft = self._open_draft(self.user_a)
        as_user = draft.with_user(self.user_b)
        calls, patcher = self._record_attachment_searches()
        with patcher:
            as_user.fields_get(["attachment_ids"])
            as_user.get_views([(False, "form"), (False, "search")])
            as_user._read_group_groupby(
                self.Draft._table, "attachment_ids", self.Draft._search([])
            )
        self.assertTrue(
            all(calls), "attachment_ids must not run an access-checked scan"
        )

    def test_attachment_list_is_the_same_for_admin_and_internal_user(self):
        draft = self._open_draft(self.user_a)
        att1 = self._attach(draft, "one.txt")
        att2 = self._attach(draft, "two.txt")
        self.env.invalidate_all()
        as_admin = draft.with_user(self.env.ref("base.user_admin"))
        as_user = draft.with_user(self.user_b)
        self.assertEqual(as_admin.attachment_ids, att1 | att2)
        self.assertEqual(as_user.attachment_ids, att1 | att2)
        self.assertEqual(
            sorted(as_user.read(["attachment_ids"])[0]["attachment_ids"]),
            sorted((att1 | att2).ids),
        )

    def test_attachments_stay_read_only_after_discard(self):
        draft = self._open_draft(self.user_a)
        self._attach(draft, "a.txt")
        draft.action_discard()
        with self.assertRaises(UserError):
            draft.write({"attachment_ids": [Command.clear()]})

    def test_form_loads_and_saves_for_internal_user(self):
        draft = self._open_draft(self.user_a)
        self._attach(draft, "a.txt")
        with Form(draft.with_user(self.user_b)) as form:
            form.subject = "Updated subject"
        self.assertEqual(draft.subject, "Updated subject")
        self.assertEqual(len(draft.attachment_ids), 1)
