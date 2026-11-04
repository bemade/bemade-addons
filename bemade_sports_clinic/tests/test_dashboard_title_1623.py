"""Task 1623 — the app home page is titled « Dashboard » / « Tableau de
bord » instead of « Teams » / « Équipes » (owner 2026-10-18). Synthetic
fixtures only (this repository is public).

Acceptance criteria:

* UC-T1 /my/home: the app bar title and the document <title> read
  « Dashboard » (no more « Teams »).
* UC-T2 The teams menu entry (/my/teams, « Teams ») and the teams list page
  title (« My teams ») are unchanged.
* UC-T3 French (fr_CA): the home reads « Tableau de bord »; the menu entry
  still reads « Équipes ».
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _title(tree):
    return tree.xpath('normalize-space(//*[contains(@class, "o_sc_appbar_title_text")])')


def _doc_title(tree):
    return tree.xpath('normalize-space(//head/title)')


@tagged('post_install', '-at_install')
class TestDashboardTitle1623(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def test_home_is_the_dashboard(self):
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get('/my/home')
            self.assertEqual(_title(tree), 'Dashboard')
            self.assertTrue(_doc_title(tree).startswith('Dashboard'), _doc_title(tree))
            self.assertNotIn('Teams', _doc_title(tree))

    def test_teams_entry_unchanged(self):
        self._login_tp()
        _text, tree = self._get('/my/home')
        labels = [' '.join(a.text_content().split())
                  for a in tree.xpath('//a[@data-sc-nav-key="teams"]')]
        self.assertTrue(labels)
        self.assertTrue(all(label == 'Teams' for label in labels), labels)
        _text, tree = self._get('/my/teams')
        self.assertEqual(_title(tree), 'My teams')


@tagged('post_install', '-at_install')
class TestDashboardTitleFrench1623(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_dashboard_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/home')
        self.assertIn('<span class="o_sc_appbar_title_text">Tableau de bord</span>', text)
        self.assertIn('<title>Tableau de bord', text)
        self.assertIn('Équipes', text)  # the menu entry
