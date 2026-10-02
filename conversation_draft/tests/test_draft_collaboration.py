# Acceptance criteria (collaborative shared drafts):
#   * The draft body is saved through the core collaborative-editing
#     history check: a save made from a diverging history is refused.
#   * The draft form opens and saves like a user would use it.
#   * "Who is editing" is a signal derived from saves: it names the last
#     editor, restarts when the editor changes, and goes quiet after the idle
#     timeout.

from datetime import datetime

from freezegun import freeze_time

from odoo.exceptions import ValidationError
from odoo.tests import Form
from odoo.tools import mute_logger

from .common import DraftCommon


class TestDraftCollaboration(DraftCommon):
    def test_diverging_history_is_refused(self):
        draft = self._open_draft()
        draft.write({"body": '<p data-last-history-steps="1,2">x</p>'})
        self.assertIn("data-last-history-steps", draft.body)
        with (
            self.assertRaises(ValidationError),
            mute_logger("odoo.addons.html_editor.tools"),
        ):
            draft.write({"body": '<p data-last-history-steps="3">y</p>'})
        draft.write({"body": '<p data-last-history-steps="2,4">z</p>'})
        self.assertIn('data-last-history-steps="4"', draft.body)

    def test_form_smoke(self):
        draft = self._open_draft()
        with Form(draft) as form:
            form.subject = "Hello"
            form.body = "<p>Hi there</p>"
            form.transport_id = self.t2
            with form.recipient_ids.new() as line:
                line.mode = "bcc"
                line.email = "form@example.com"
        self.assertEqual(draft.subject, "Hello")
        self.assertEqual(draft.transport_id, self.t2)
        self.assertIn("form@example.com", draft.recipient_ids.mapped("email"))

    def test_editing_signal(self):
        t0 = datetime(2026, 3, 2, 9, 0, 0)
        with freeze_time(t0):
            draft = self._open_draft(self.user_a)
            self.assertEqual(draft.editor_id, self.user_a)
            self.assertEqual(draft.editing_since, t0)
            self.conversation.invalidate_recordset()
            self.assertEqual(self.conversation.draft_editor_id, self.user_a)
        with freeze_time("2026-03-02 09:05:00"):
            draft.write({"subject": "five minutes in"})
            self.assertEqual(draft.editing_since, t0)
        with freeze_time("2026-03-02 09:20:00"):
            draft.invalidate_recordset()
            self.conversation.invalidate_recordset()
            self.assertFalse(draft.is_being_edited)
            self.assertFalse(self.conversation.draft_editor_id)
            draft.with_user(self.user_b).write({"subject": "B takes over"})
            self.assertEqual(draft.editor_id, self.user_b)
            self.assertEqual(draft.editing_since, datetime(2026, 3, 2, 9, 20, 0))
