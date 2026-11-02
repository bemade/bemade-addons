"""Task 1736 — the card top bars in a real browser (the web client's
behaviour: edit-only trash, chevron-only fold, ★ toggle, confirmations, undo
toast), on a phone (390 px) and a laptop (1366 px). Synthetic fixtures only
(this repository is public). Tours: static/tests/tours/
sc_card_top_bars_1736_tours.js.

Acceptance criteria (see test_card_top_bars_1736.py for the server side):

* AC-T1 Injury card: a tap on the header never folds / unfolds it, the
  chevron does; the header pencil edits the Details (unfolding a folded
  card) and shows the red trash left of the ✓, which hides again on close;
  the trash opens « Delete injury »'s confirmation.
* AC-T2 Player header: the ★ follows / unfollows in place (filled while
  following), left of the pencil.
* AC-T3 Emergency contact: the trash shows while editing only, asks first.
* AC-T4 Medical item: the trash asks first (« Cancel » keeps the item,
  « Delete » removes it).
* AC-T5 Quick note: the archive icon archives; the toast's « Undo » puts it
  back.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_card_top_bars_1736 import TopBars1736Common

LOGIN = 'pc.tp@example.com'


class _TopBarTours1736:

    def test_injury_card(self):
        url = '/my/player?player_id=%s&team_id=%s&tab=injuries' % (self.player.id, self.team_a.id)
        self.start_tour(url, 'sc_1736_injury', login=LOGIN)

    def test_star(self):
        url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        self.start_tour(url, 'sc_1736_star', login=LOGIN)

    def test_contact(self):
        url = '/my/player?player_id=%s&team_id=%s&tab=info' % (self.player.id, self.team_a.id)
        self.start_tour(url, 'sc_1736_contact', login=LOGIN)

    def test_medical_delete_confirm(self):
        url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        self.start_tour(url, 'sc_1736_med_delete', login=LOGIN)
        self.assertFalse(self.env['sports.patient.critical.item'].sudo().search(
            [('patient_id', '=', self.player.id)]))

    def test_quick_note_undo(self):
        self.start_tour('/my/notepad', 'sc_1736_note_undo', login=LOGIN)
        self.qnote.invalidate_recordset()
        self.assertTrue(self.qnote.active)


@tagged('post_install', '-at_install')
class TestCardTopBarsPhone1736(_TopBarTours1736, TopBars1736Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestCardTopBarsLaptop1736(_TopBarTours1736, TopBars1736Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
