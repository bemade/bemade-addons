"""Task 1644 — the upload sheet on a phone (static/tests/tours/
sc_upload_sheet_1644_tours.js, 390 px). Synthetic fixtures only.

Acceptance criteria covered here:

* AC-1 Both callers — the player's Documents tab (now a sheet opened by
  « + Ajouter », like the injury card) and the injury card's « Add
  documents »: with six files the sheet head (the picker) and the Upload bar
  stay in view and only the middle scrolls.
* AC-2 On a phone the drop zone reads « Add files » (a button on the same
  file input).
* AC-3 Upload turns « Uploading… » (disabled, aria-busy, Cancel / Escape
  held), a second submit is refused, a page shown again is idle again; the
  player tab's upload stores the six documents.
* AC-4 The Documents tab renders the sheet, not the old inline panel
  (test_list_header_1607 / test_review_fixes_1018b updated).

The iPhone keyboard, the native picker and momentum scrolling stay
UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_injury_quick_tours_1604 import QuickToursCommon


@tagged('post_install', '-at_install')
class TestUploadSheetTours1644(QuickToursCommon):
    browser_size = '390x844'

    def test_player_tab(self):
        self.start_tour('/my/player?player_id=%s&tab=documents' % self.player.id,
                        'sc_1644_player_tab', login='pc.tp@example.com')
        docs = self.env['sports.injury.document'].search([('patient_id', '=', self.player.id)])
        self.assertEqual(len(docs.filtered(lambda d: (d.file_name or '').startswith('Synthetic 1644'))), 6)

    def test_injury_card(self):
        self.start_tour('/my/player?player_id=%s&tab=injuries&injury=%s' % (self.player.id, self.injury.id),
                        'sc_1644_injury_card', login='pc.tp@example.com')
