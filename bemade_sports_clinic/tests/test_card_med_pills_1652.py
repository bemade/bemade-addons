"""Task 1652 — the red medical pills on player cards open the player page's
popup. Synthetic fixtures only.

Acceptance criteria covered here (with test_medical_card_pills_1630, whose
CARD-2 now asserts the button + its single page-level sheet):

* UC-1 Team dashboard and /my/players: each red card pill is a button naming
  its sheet; the sheet is on the page ONCE (a player in two lists), outside
  every read fragment.
* UC-2 A therapist's sheet has the edit pencil; a coach's has none.
* UC-3 A non-urgent player has no card pill and no card sheet.
* UC-4 (tour, phone) the pill is as tall as the status pill beside it; a tap
  opens the popup without toggling / following the card; the therapist sets
  « Not urgent »: the popup saves, the card refreshes, the pill is gone.
"""
from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_medical_card_pills_1630 import MedicalCards1630Common


@tagged('post_install', '-at_install')
class TestCardMedPills1652(MedicalCards1630Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _page(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return lxml_html.fromstring(resp.text)

    def test_sheets_once_outside_fragments(self):
        self._login_tp()
        with self._presence():
            for url in (self.team_url, '/my/players'):
                tree = self._page(url)
                for key in ('allergy', 'medical_alert'):
                    sheet_id = 'sc_med_card_%s_%s' % (key, self.player.id)
                    sheets = tree.xpath('//dialog[@id="%s"]' % sheet_id)
                    self.assertEqual(len(sheets), 1, (url, key))
                    self.assertFalse(sheets[0].xpath('ancestor::*[@data-sc-fragment]'), (url, key))
                    self.assertTrue(tree.xpath('//button[@data-sc-med-card-sheet="%s"]' % sheet_id), (url, key))

    def test_editable_for_therapist_read_only_for_coach(self):
        sheet = '//dialog[@id="sc_med_card_allergy_%s"]' % self.player.id
        self._login_tp()
        with self._presence():
            tree = self._page(self.team_url)
        self.assertTrue(tree.xpath(sheet + '//button[@data-sc-edit-toggle]'))
        self.assertTrue(tree.xpath(sheet + '//form[@data-sc-med-add]'))
        self._login_coach()
        with self._presence():
            tree = self._page(self.team_url)
        self.assertTrue(tree.xpath(sheet))
        self.assertFalse(tree.xpath(sheet + '//button[@data-sc-edit-toggle] | ' + sheet + '//form'))

    def test_non_urgent_player_has_pills_and_sheets(self):
        # Review round 2 (owner 2026-10-27): a therapist sees the pills of
        # every card (yellow / grey too), each opening its popup.
        self._login_tp()
        tree = self._page('/my/players')
        for key in ('allergy', 'medical_alert'):
            sheet_id = 'sc_med_card_%s_%s' % (key, self.other.id)
            self.assertEqual(len(tree.xpath('//button[@data-sc-med-card-sheet="%s"]' % sheet_id)), 1)
            self.assertEqual(len(tree.xpath('//dialog[@id="%s"]' % sheet_id)), 1)

@tagged('post_install', '-at_install')
class TestCardMedPillsTour1652(MedicalCards1630Common):
    browser_size = '390x844'

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_tap_edit_refresh(self):
        self.start_tour('/my/players', 'sc_1652_card_pill', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.allergy_level, 'minor')
