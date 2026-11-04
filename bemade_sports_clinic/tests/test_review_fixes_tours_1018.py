"""Review fixes 2026-10-18 — browser tours
(static/tests/tours/sc_review_fixes_1018_tours.js). Synthetic fixtures only.

Acceptance criteria covered here (laptop 1366 px and phone 390 px):

* RF-HEADER The player header opens as a read view (status chips, no
  selector, no « Remove player »); its one pencil opens the edit view with
  the recommendation, both return dates and « Remove player » (task 1630:
  no allergies — the header's pills); the recommendation saved there shows
  in the read view after « Done », without a reload.
* RF-DATES On an injury card, picking « Resolved » hides the predicted
  resolution date field and shows the resolution date field, in place; the
  predicted date is cleared on the record.

The look in both themes stays UNVERIFIED here — the dev-review click-through
covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


class _Tours1018:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.team_ids = [(4, cls.team_a.id)]
        cls.injury.sudo().write({'predicted_resolution_date': '2030-03-01'})

    def test_header_pencil(self):
        url = '/my/player?player_id=%s&team_id=%s&tab=injuries' % (self.player.id, self.team_a.id)
        self.start_tour(url, 'sc_1018_header_pencil', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.training_recommendation, 'Synthetic latex')

    def test_injury_dates(self):
        url = '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id)
        self.start_tour(url, 'sc_1018_injury_dates', login='pc.tp@example.com')
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertFalse(self.injury.predicted_resolution_date)


@tagged('post_install', '-at_install')
class TestReviewFixesToursLaptop1018(_Tours1018, PlayerInlineCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestReviewFixesToursPhone1018(_Tours1018, PlayerInlineCommon):
    browser_size = '390x844'
    allow_inherited_tests_method = True
