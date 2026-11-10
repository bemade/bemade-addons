"""Task 1746 — phone: one tap home from any shell sub-page. Synthetic
fixtures only.

On a phone the bottom tabs carry no dashboard tab and a sub-page shows the
back chevron where the top-level pages show the logo, so going home took a
tap on « back » per level. Owner decision (2026-11-03): keep the chevron and
put the small Fit Crew picto right after it; the picto goes to the dashboard.

Acceptance criteria covered here:

* UC-P1 Every sub-page (team, player, injury card, event, activity, « More »
  pages) renders the home picto in the app bar, RIGHT AFTER the back chevron:
  a link to ``/my/home`` with the accessible label « Dashboard » (aria-label
  and title — « Tableau de bord » in French), the same mark as the logo.
* UC-P2 A top-level page (dashboard, teams, players, activities, « More »)
  is unchanged: the logo, no back chevron, no home picto.
* UC-P3 (phone 390 px, browser) On a sub-page the picto is visible, sits
  between the chevron and the title, is a ≥ 44 px tap target, leaves the
  title truncating (ellipsis, no overflow) and the right-hand icons where a
  top-level page has them; tapping it opens the dashboard.
* UC-P4 (laptop 1366 px, browser) The picto is hidden (the rail's brand
  already goes home); the back chevron + trail are unchanged.
* UC-P5 French: the picto's label is « Tableau de bord ».
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_nav_1579 import Nav1579Common

HOME = '/my/home'
PICTO = '//header[contains(@class, "o_sc_appbar")]//a[contains(concat(" ", @class, " "), " o_sc_home_picto ")]'


class _Picto1746(Nav1579Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.activity = env['mail.activity'].create({
            'res_model_id': env['ir.model']._get('sports.patient').id,
            'res_id': cls.player.id,
            'activity_type_id': env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Synthetic 1746 follow-up',
            'user_id': cls.tp.id,
            'date_deadline': fields.Date.today() + timedelta(days=1),
        })
        cls.player_url = '/my/player?player_id=%s&team_id=%s' % (cls.player.id, cls.team_a.id)
        cls.sub_pages = [
            cls.team_url,
            cls.player_url,
            '/my/injury/edit?injury_id=%s' % cls.injury.id,
            '/my/event/%s' % cls.clinic.id,
            '/my/activity/%s' % cls.activity.id,
            '/my/app/settings',
        ]
        cls.top_pages = [HOME, '/my/teams', '/my/players', '/my/activities', '/my/app/more']


@tagged('post_install', '-at_install')
class TestHomePicto1746(_Picto1746):

    # -- UC-P1 -----------------------------------------------------------
    def test_sub_pages_have_the_home_picto_after_back(self):
        for url in self.sub_pages:
            _text, tree = self._get(url)
            picto = tree.xpath(PICTO)
            self.assertEqual(len(picto), 1, url)
            picto = picto[0]
            self.assertEqual(picto.get('href'), HOME, url)
            self.assertEqual(picto.get('aria-label'), 'Dashboard', url)
            self.assertEqual(picto.get('title'), 'Dashboard', url)
            self.assertTrue(picto.xpath('.//img[contains(@class, "o_sc_logo_mark")]'), url)
            # Right after the chevron, before the title.
            previous = picto.getprevious()
            self.assertIsNotNone(previous, url)
            self.assertIn('o_sc_back', previous.get('class', '').split(), url)
            following = picto.getnext()
            self.assertEqual(following.tag, 'h1', url)
            self.assertIn('o_sc_appbar_title', following.get('class', ''), url)
            # The sub-page has no top-level logo.
            self.assertFalse(tree.xpath('//header//a[contains(concat(" ", @class, " "), " o_sc_logo ")]'), url)

    # -- UC-P2 -----------------------------------------------------------
    def test_top_level_pages_unchanged(self):
        for url in self.top_pages:
            _text, tree = self._get(url)
            self.assertFalse(tree.xpath(PICTO), url)
            self.assertFalse(tree.xpath('//header//a[@data-pk-back]'), url)
            self.assertEqual(
                tree.xpath('//header//a[contains(concat(" ", @class, " "), " o_sc_logo ")]/@href'),
                [HOME], url)

    def test_coach_sub_page_has_the_picto(self):
        self._login_coach()
        _text, tree = self._get(self.player_url)
        self.assertEqual(tree.xpath(PICTO + '/@href'), [HOME])


@tagged('post_install', '-at_install')
class TestHomePictoPhone1746(_Picto1746):
    browser_size = '390x844'

    # -- UC-P3 -----------------------------------------------------------
    def test_phone_picto_goes_home(self):
        self.start_tour(self.player_url, 'sc_1746_phone_home_picto', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestHomePictoLaptop1746(_Picto1746):
    browser_size = '1366x768'

    # -- UC-P4 -----------------------------------------------------------
    def test_laptop_picto_hidden(self):
        self.start_tour(self.player_url, 'sc_1746_laptop_no_picto', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestHomePictoFr1746(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    # -- UC-P5 -----------------------------------------------------------
    def test_picto_label_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/team?team_id=%s' % self.team_a.id)
        self.assertIn('class="o_sc_home_picto" aria-label="Tableau de bord" title="Tableau de bord"', text)
