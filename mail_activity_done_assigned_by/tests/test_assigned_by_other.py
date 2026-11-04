"""Use case 2: created by A, assigned to and closed by B.

Acceptance criteria
-------------------
* The "done" message gets, under its title, the line
  ``Assigned by <A> on <creation date> · due <deadline>``
  (FR: ``Assigné par <A> le <date> · échéance <date>``).
* Dates use the closer's language format and timezone (the creation
  timestamp is converted to the closer's timezone before taking the date).
* The core title is unchanged and carries no "(originally assigned to ...)"
  since the assignee closed it.
* Feedback and attachments are still posted on the message.
* Holds through ``action_feedback`` and ``action_done``.
"""

from odoo.tests import tagged

from .common import ActivityDoneCase

EXPECTED = {
    "en_US": "Assigned by Alice Creator on 03/04/2026 · due 03/20/2026",
    "fr_FR": "Assigné par Alice Creator le 04/03/2026 · échéance 20/03/2026",
}


@tagged("post_install", "-at_install")
class TestAssignedByOther(ActivityDoneCase):
    def test_line_rendered(self):
        for via in ("action_feedback", "action_done"):
            for lang, expected in EXPECTED.items():
                with self.subTest(via=via, lang=lang):
                    activity = self._schedule(self.alice, self.bob)
                    message = self._mark_done(activity, self.bob, lang, via)
                    self.assertEqual(self._assigned_by_line(message.body), expected)
                    title = self._title(message.body)
                    self.assertIn("Call back the customer", title)
                    self.assertNotIn("Bob Assignee", title)
                    self.assertNotIn("Alice Creator", title)

    def test_title_in_english_unchanged(self):
        activity = self._schedule(self.alice, self.bob)
        message = self._mark_done(activity, self.bob, "en_US", "action_done")
        self.assertEqual(self._title(message.body), "To-Do done : Call back the customer")

    def test_feedback_and_attachments_kept(self):
        activity = self._schedule(self.alice, self.bob)
        attachment = self.env["ir.attachment"].create(
            {
                "name": "report.txt",
                "raw": b"synthetic",
                "res_model": "mail.activity",
                "res_id": activity.id,
            }
        )
        message = self._mark_done(
            activity, self.bob, "en_US", "action_feedback",
            feedback="Left a voicemail\nWill retry",
        )
        self.assertIn("Left a voicemail", str(message.body))
        self.assertIn("Will retry", str(message.body))
        self.assertIn(attachment, message.attachment_ids)
        self.assertEqual(
            self._assigned_by_line(message.body), EXPECTED["en_US"]
        )
