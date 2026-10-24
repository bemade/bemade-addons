"""Use case 1: the creator closes the activity -> core message unchanged.

Acceptance criteria
-------------------
* An activity a user scheduled for themselves and marks as done themselves
  produces the core "done" message with NO "Assigned by" / "Created
  automatically" line.
* Same when the creator scheduled it for someone else but closes it
  themselves (creator = closer): no line; the core "(originally assigned to
  X)" mention is still shown.
* Holds through ``action_feedback`` and ``action_done``, in English and in
  French.
"""

from odoo.tests import tagged

from .common import ActivityDoneCase


@tagged("post_install", "-at_install")
class TestSelfAssigned(ActivityDoneCase):
    def test_self_assigned_no_line(self):
        for via in ("action_feedback", "action_done"):
            for lang in ("en_US", "fr_FR"):
                with self.subTest(via=via, lang=lang):
                    activity = self._schedule(self.alice, self.alice)
                    message = self._mark_done(activity, self.alice, lang, via)
                    self.assertIsNone(self._assigned_by_line(message.body))
                    self.assertNotIn("Alice Creator", self._title(message.body))

    def test_creator_closes_activity_assigned_to_other(self):
        for via in ("action_feedback", "action_done"):
            for lang in ("en_US", "fr_FR"):
                with self.subTest(via=via, lang=lang):
                    activity = self._schedule(self.alice, self.bob)
                    message = self._mark_done(activity, self.alice, lang, via)
                    self.assertIsNone(self._assigned_by_line(message.body))
                    # core "(originally assigned to Bob)" untouched
                    self.assertIn("Bob Assignee", self._title(message.body))
