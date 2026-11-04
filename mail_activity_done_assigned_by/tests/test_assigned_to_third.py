"""Use case 3: created by A, assigned to B, closed by C.

Acceptance criteria
-------------------
* The line ``Assigned by <A> on <date> · due <deadline>`` is shown
  (FR: ``Assigné par <A> le <date> · échéance <date>``).
* The core "(originally assigned to <B>)" mention is still in the title.
* Holds through ``action_feedback`` and ``action_done``, EN and FR.
"""

from odoo.tests import tagged

from .common import ActivityDoneCase

EXPECTED = {
    "en_US": "Assigned by Alice Creator on 03/04/2026 · due 03/20/2026",
    "fr_FR": "Assigné par Alice Creator le 04/03/2026 · échéance 20/03/2026",
}


@tagged("post_install", "-at_install")
class TestAssignedToThird(ActivityDoneCase):
    def test_line_and_original_assignee(self):
        for via in ("action_feedback", "action_done"):
            for lang, expected in EXPECTED.items():
                with self.subTest(via=via, lang=lang):
                    activity = self._schedule(self.alice, self.bob)
                    message = self._mark_done(activity, self.carol, lang, via)
                    self.assertEqual(self._assigned_by_line(message.body), expected)
                    self.assertIn("Bob Assignee", self._title(message.body))

    def test_original_assignee_wording_en(self):
        activity = self._schedule(self.alice, self.bob)
        message = self._mark_done(activity, self.carol, "en_US", "action_done")
        self.assertIn("(originally assigned to Bob Assignee)", self._title(message.body))
