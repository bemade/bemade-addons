"""Task 1646 — add panels never auto-focus a select / picker; phones focus
nothing (static/tests/tours/sc_add_panel_focus_1646_tours.js). Synthetic
fixtures only.

Acceptance criteria covered here:

* AC-1 Laptop: « + Ajouter » of the player's Notes list focuses the note
  textarea, not « Link to Injury » (a select).
* AC-2 Touch screen (coarse pointer, stubbed): nothing in the panel is
  focused.

The real iPhone (no native picker, no keyboard) stays UNVERIFIED until
/dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_injury_quick_tours_1604 import QuickToursCommon


@tagged('post_install', '-at_install')
class TestAddPanelFocusTours1646(QuickToursCommon):

    def _notes(self):
        return '/my/player?player_id=%s&tab=notes' % self.player.id

    def test_notes_laptop(self):
        self.start_tour(self._notes(), 'sc_1646_notes_laptop', login='pc.tp@example.com')

    def test_notes_touch(self):
        self.start_tour(self._notes(), 'sc_1646_notes_touch', login='pc.tp@example.com')
