"""Task 1793 (epic #1535, P4b), review round 2 — the app's list pager
speaks French. Synthetic fixtures.

Odoo's ``portal.pager`` names its chevrons « Previous » / « Next » in its own
view and Odoo's catalogue leaves those terms untranslated; a clinic
catalogue entry cannot safely reach another module's view. The app lists
call the clinic's ``bemade_sports_clinic.app_pager`` instead, whose labels
are clinic terms.

Acceptance criteria covered here:

* UC-P1 A paged app list (players) rendered for a fr_CA user names its
  pager links « Précédent » / « Suivant » (aria-label and title), and no
  English « Previous » / « Next » is left in the shell.
* UC-P2 The pager keeps Odoo's behaviour: page links, the current page
  marked (``aria-current``), the previous link disabled on page 1.
* UC-P3 No app template of the clinic calls ``portal.pager`` any more.
"""
import glob
import os
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import Command
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestAppPagerI18n1793(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A second player on the therapist's team: two pages at one a page.
        cls.player_c = cls.env['sports.patient'].create({'first_name': 'Pat', 'last_name': 'Three'})
        cls.player_c.team_ids = [Command.set([cls.team_a.id])]

    def _paged(self, url):
        with patch.object(CustomerPortal, '_items_per_page', 1):
            tree = lxml_html.fromstring(self._fr(url))
        shell = self._shell(tree)
        self.assertIsNotNone(shell, url)
        pagers = shell.xpath('.//*[contains(concat(" ", @class, " "), " o_pk_pager ")]')
        self.assertTrue(pagers, 'no pager on %s' % url)
        return shell, pagers[0]

    # -- UC-P1 / UC-P2 ---------------------------------------------------
    def test_players_pager_in_french(self):
        self._switch(True)
        self._login_tp()
        shell, pager = self._paged('/my/players')
        links = pager.xpath('.//a[contains(@class, "page-link")]')
        labels = [(a.get('aria-label'), a.get('title')) for a in links if a.get('aria-label')]
        self.assertEqual(labels, [('Précédent', 'Précédent'), ('Suivant', 'Suivant')])
        html = lxml_html.tostring(shell, encoding='unicode')
        self.assertNotIn('"Previous"', html)
        self.assertNotIn('"Next"', html)
        # Page 1: previous disabled, page 1 is the current one, page 2 linked.
        items = pager.xpath('./ul/li')
        self.assertIn('disabled', items[0].get('class'))
        self.assertEqual(pager.xpath('.//a[@aria-current="page"]/text()'), ['1'])
        self.assertTrue(pager.xpath('.//a[text()="2"]/@href'))

    # -- UC-P3 -----------------------------------------------------------
    def test_no_app_template_calls_portal_pager(self):
        root = get_module_path('bemade_sports_clinic')
        offenders = []
        for path in sorted(glob.glob(os.path.join(root, 'views', 'sc_*.xml'))):
            with open(path, encoding='utf-8') as handle:
                if 't-call="portal.pager"' in handle.read():
                    offenders.append(os.path.basename(path))
        self.assertFalse(offenders, 'app templates calling portal.pager: %s' % offenders)
