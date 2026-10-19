"""Task 1611 — the player page follows its in-place saves (read fragments).
Synthetic fixtures only.

Use case: on the player page a therapist edits the player's name, date of
birth, allergies or teams; the title, the hero and the dependent rows show the
new data at once — they used to wait for a reload (or « Done »).

Acceptance criteria (each: the save refreshes the fragment, and the fragment
then shows the new value):

* AC-P1 Name / jersey -> the app bar title, the crumb, the document title and
  the hero (initials, « Last, First », position).
* AC-P2 Date of birth -> the Identity card's « Age » row.
* AC-P3 Allergies -> the hero « Allergies » banner, shown when filled and
  gone when cleared (its holder is always rendered).
* AC-P4 Teams -> the hero team links, the memberships list, the removal
  actions and their sheets.
* AC-P5 Play status -> the coach's read-only status chips.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon


@tagged('post_install', '-at_install')
class TestFragmentsPlayer1611(FragmentsCommon):

    def _url(self, tab='info'):
        return '/my/player?player_id=%s&tab=%s&team_id=%s' % (self.player.id, tab, self.team_a.id)

    def _key(self, part):
        return 'sports.patient:%s:%s' % (self.player.id, part)

    # -- AC-P1 -------------------------------------------------------------
    def test_name_refreshes_title_crumb_and_hero(self):
        self._login_tp()
        payload = self._saved(self.player, 'last_name', 'Renamed', confirm='1')
        payload = self._saved(self.player, 'jersey_number', '42')
        for part in ('appbar', 'crumb', 'hero-head'):
            self.assertRefreshes(payload, self._key(part))
        answer = self._fragments(self._url(), [self._key('appbar'), self._key('crumb'), self._key('hero-head')])
        self.assertIn('Renamed', answer['title'])
        self.assertIn('#42', answer['title'])
        for part in ('appbar', 'crumb'):
            self.assertIn('Renamed', answer['fragments'][self._key(part)])
        hero = self._fragment(self._url(), self._key('hero-head'))
        self.assertEqual(self._text(hero.xpath('.//*[contains(@class, "o_sc_avatar")]')[0]), 'PR')
        self.assertIn('Renamed', self._text(hero.xpath('.//h2')[0]))

    # -- AC-P2 -------------------------------------------------------------
    def test_dob_refreshes_age(self):
        self._login_tp()
        dob = date.today() - relativedelta(years=15, days=3)
        payload = self._saved(self.player, 'date_of_birth', dob.isoformat(), confirm='1')
        self.assertRefreshes(payload, self._key('identity'))
        identity = self._fragment(self._url(), self._key('identity'))
        rows = dict(zip([self._text(dt) for dt in identity.xpath('.//dt')],
                        [self._text(dd) for dd in identity.xpath('.//dd')]))
        self.assertEqual(rows.get('Age'), '15')
        self.assertFragmentMatchesPage(self._url(), self._key('identity'))

    # -- AC-P3 -------------------------------------------------------------
    def test_allergies_banner_shows_and_hides(self):
        self._login_tp()
        tree = self._page(self._url())
        holder = self._node(tree, self._key('allergies'))
        self.assertIsNotNone(holder, 'the holder is rendered even without allergies')
        self.assertFalse(holder.xpath('.//*[contains(@class, "o_sc_banner")]'))
        payload = self._saved(self.player, 'allergies', 'Synthetic peanuts')
        self.assertRefreshes(payload, self._key('allergies'))
        banner = self._fragment(self._url(), self._key('allergies'))
        self.assertIn('Synthetic peanuts', self._text(banner))
        self.assertTrue(banner.xpath('.//*[contains(@class, "o_sc_banner")]'))
        self._saved(self.player, 'allergies', '')
        banner = self._fragment(self._url(), self._key('allergies'))
        self.assertFalse(banner.xpath('.//*[contains(@class, "o_sc_banner")]'))

    # -- AC-P4 -------------------------------------------------------------
    def test_teams_refresh_links_memberships_and_actions(self):
        team_c = self.env['sports.team'].create({'name': 'PC Team C', 'parent_id': self.org.id})
        self.env['sports.team.staff'].create({
            'team_id': team_c.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist'})
        self._login_tp()
        payload = self._saved(self.player, 'sc_team_ids', '%s,%s' % (self.team_a.id, team_c.id))
        for part in ('hero-head', 'memberships', 'hero-actions', 'removal-sheets'):
            self.assertRefreshes(payload, self._key(part))
        hero = self._fragment(self._url(), self._key('hero-head'))
        self.assertEqual(sorted(hero.xpath('.//a[@data-sc-row-link="sports.team"]/text()')),
                         ['PC Team A', 'PC Team C'])
        members = self._fragment(self._url(), self._key('memberships'))
        self.assertIn('PC Team C', self._text(members))
        self.assertFragmentMatchesPage(self._url(), self._key('hero-actions'))
        # Team A untied: its row and links go.
        self._saved(self.player, 'sc_team_ids', str(team_c.id))
        url = '/my/player?player_id=%s&tab=info' % self.player.id
        members = self._fragment(url, self._key('memberships'))
        self.assertNotIn('PC Team A', self._text(members))
        hero = self._fragment(url, self._key('hero-head'))
        self.assertEqual(hero.xpath('.//a[@data-sc-row-link="sports.team"]/text()'), ['PC Team C'])
        self.assertFragmentMatchesPage(url, self._key('removal-sheets'))

    # -- AC-P5 -------------------------------------------------------------
    def test_status_refreshes_coach_chips(self):
        self._login_tp()
        payload = self._saved(self.player, 'sc_status', 'no:no')
        self.assertRefreshes(payload, self._key('status'))
        self._login_coach()
        chips = self._fragment(self._url(), self._key('status'))
        self.assertTrue(chips.xpath('.//*[contains(@class, "o_sc_chip_red")]'))
