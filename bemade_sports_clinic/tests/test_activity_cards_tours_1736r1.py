"""Task 1736 r1 — an activity card edited in place in a real browser (the
web client's behaviour: the fields mounted on the first pencil tap, the
edit-only trash, autosave, the ✓, the details popout, « Done »), on a phone
(390 px) and a laptop (1366 px). Synthetic fixtures only (this repository
is public). Tour: static/tests/tours/sc_activity_cards_1736r1_tours.js.

Acceptance criteria (see test_activity_cards_1736r1.py for the server side):

* AC-T1 The card's trash is hidden until its pencil (rightmost) is tapped;
  the pencil mounts the fields (summary, due date, assignee, note) and
  becomes the ✓; the trash shows left of it and asks first.
* AC-T2 The due date, the assignee and the note save as they change; the ✓
  closes the card and the card shows the new due date (no reload).
* AC-T3 A tap on the card opens its details popout on the same page (the
  new note, the creator).
* AC-T4 « Done » is the card's last action and completes the activity.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_activity_cards_1736r1 import ActivityCards1736r1Common


class _ActivityCardTour1736r1:

    def test_activity_card(self):
        self._switch(True)
        url = '/my/player?player_id=%s&tab=activities&x1736=%s&xuser=%s' % (
            self.player.id, self.act_player.id, self.coach.id)
        self.start_tour(url, 'sc_1736r1_activity_card', login='pc.tp@example.com')
        activity = self.act_player.with_context(active_test=False)
        activity.invalidate_recordset()
        self.assertFalse(activity.active, 'completed (« Done »)')
        self.assertEqual(str(activity.date_deadline), '2031-05-06')
        self.assertEqual(activity.user_id, self.coach)
        self.assertIn('SC1736r1 tour note', activity.note)


@tagged('post_install', '-at_install')
class TestActivityCardPhone1736r1(_ActivityCardTour1736r1, ActivityCards1736r1Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestActivityCardLaptop1736r1(_ActivityCardTour1736r1, ActivityCards1736r1Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
