"""Task 1642 — after an edit, the screen comes back to the top of the block
just edited (static/tests/tours/sc_edit_anchor_1642_tours.js, phone
390 px). Synthetic fixtures only.

Acceptance criteria covered here:

* AC-1 Injury card notes: leaving the notes field (after the page jumped
  away) brings the Notes block's top back just below the app bar.
* AC-2 The injury card's « Terminé » brings the collapsed card's top back
  just below the app bar (was scrollIntoView « nearest »).
* AC-3 A player info group (the medical card): its « Done » brings the
  card's top back just below the app bar.
* AC-4 A touch after the edit cancels the anchor (never fight the user).

The real phone keyboard closing cannot be reproduced headless — UNVERIFIED
until the /dev-review tap-through.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_injury_quick_tours_1604 import QuickToursCommon


@tagged('post_install', '-at_install')
class TestEditAnchorTours1642(QuickToursCommon):
    browser_size = '390x844'

    def _injury_url(self):
        return '/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id)

    def test_injury_notes_blur(self):
        self.start_tour(self._injury_url(), 'sc_1642_injury_notes_blur', login='pc.tp@example.com')

    def test_injury_done(self):
        self.start_tour(self._injury_url(), 'sc_1642_injury_done', login='pc.tp@example.com')

    def test_player_group_done(self):
        self.start_tour('/my/player?player_id=%s&tab=info' % self.player.id,
                        'sc_1642_player_group_done', login='pc.tp@example.com')
