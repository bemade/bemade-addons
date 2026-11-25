"""Use case 4: activity created by the superuser (OdooBot), closed by a user.

Acceptance criteria
-------------------
* The line reads ``Created automatically on <date> · due <deadline>``
  (FR: ``Créée automatiquement le <date> · échéance <date>``).
* The superuser's name ("OdooBot") is never shown.
* Holds through ``action_feedback`` and ``action_done``, EN and FR.
"""

from odoo.tests import tagged

from .common import ActivityDoneCase

EXPECTED = {
    "en_US": "Created automatically on 03/04/2026 · due 03/20/2026",
    "fr_FR": "Créée automatiquement le 04/03/2026 · échéance 20/03/2026",
}


@tagged("post_install", "-at_install")
class TestCreatedAutomatically(ActivityDoneCase):
    def test_automatic_line(self):
        for via in ("action_feedback", "action_done"):
            for lang, expected in EXPECTED.items():
                with self.subTest(via=via, lang=lang):
                    activity = self._schedule(self.root, self.bob)
                    message = self._mark_done(activity, self.bob, lang, via)
                    self.assertEqual(self._assigned_by_line(message.body), expected)
                    self.assertNotIn(self.root.name, str(message.body))
