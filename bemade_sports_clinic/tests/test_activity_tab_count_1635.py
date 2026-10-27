"""Task 1635 (portal app) — the open-activity count on the Activités tab of
the player page and the team page. Synthetic fixtures only (this repository
is public).

Acceptance criteria (owner decisions 2026-10-20):

* UC-1 Player page: the Activities tab carries a small number pill = the
  open activities the tab lists (mail.activity on sports.patient/<id>, run
  as the viewer). Neutral tone; red when at least one of them is overdue
  (deadline before today in the viewer's timezone). No pill at 0.
* UC-2 Per viewer: the count is the viewer's own listing — a therapist
  counts what the record rules let them see, a coach only the activities
  assigned to or created by them. The pill equals the number of rows in
  the tab's panel.
* UC-3 Team page: the same on the team's Activities tab (team-level
  activities only: sports.team/<id>).
* UC-4 Other tabs and pages are unchanged: no pill on Injuries / Info /
  Documents / Notes, nor on the team's Overview / Players tabs, nor on the
  tabs of the activities and events pages.
* UC-5 Adding or completing an activity (a POST + redirect) shows the new
  count on the next render.
* UC-6 The pill's aria-label is translated (fr_CA): « N activités
  ouvertes », with the overdue count when there is one.
"""
from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_activity_clock_1592 import (
    Clock1592Mixin,
)
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _text(node):
    return ' '.join(node.text_content().split())


class TabCount1635Mixin(Clock1592Mixin):

    @staticmethod
    def _tab(tree, key):
        tabs = tree.xpath('//nav[@data-sc-tabs]/a[@data-sc-tab="%s"]' % key)
        return tabs[0] if tabs else None

    @staticmethod
    def _badge(tab):
        badges = tab.xpath('.//span[contains(@class, "o_sc_tab_badge")]')
        return badges[0] if badges else None

    def _assert_badge(self, tree, key, count, overdue):
        tab = self._tab(tree, key)
        self.assertIsNotNone(tab, 'no %s tab' % key)
        badge = self._badge(tab)
        if not count:
            self.assertIsNone(badge, 'a pill at 0 on the %s tab' % key)
            return None
        self.assertIsNotNone(badge, 'no pill on the %s tab' % key)
        self.assertEqual(_text(badge), str(count))
        classes = badge.get('class').split()
        tone = 'o_sc_tab_badge_red' if overdue else 'o_sc_tab_badge_neutral'
        other = 'o_sc_tab_badge_neutral' if overdue else 'o_sc_tab_badge_red'
        self.assertIn(tone, classes)
        self.assertNotIn(other, classes)
        self.assertTrue(badge.get('aria-label'))
        # Task 1647: the pill comes first, the label right after it.
        self.assertTrue(badge.getnext() is not None and 'o_sc_tab_label' in badge.getnext().get('class'))
        self.assertTrue(badge.getnext().text_content().strip())
        return badge

    def _panel_rows(self, tree):
        panel = tree.xpath('//section[@data-sc-tab-panel="activities"]')[0]
        return panel.xpath('.//*[@data-sc-activity-row]')

    def _player_activities(self):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id),
        ])


@tagged('post_install', '-at_install')
class TestActivityTabCount1635(TabCount1635Mixin, AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.player_url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        self.team_url = '/my/team?team_id=%s' % self.team_a.id

    # -- UC-1 ------------------------------------------------------------
    def test_player_tab_count_and_overdue_tone(self):
        self._login_tp()
        # Base fixtures: the therapist's player task + injury task, due today.
        _t, tree = self._get(self.player_url)
        self._assert_badge(tree, 'activities', 2, overdue=False)
        # One of the two overdue: same count, red.
        self._player_activities()[:1].write({'date_deadline': '2020-01-01'})
        _t, tree = self._get(self.player_url + '&tab=activities')
        self._assert_badge(tree, 'activities', 2, overdue=True)
        self.assertEqual(len(self._panel_rows(tree)), 2)

    def test_player_tab_no_badge_at_zero(self):
        self._player_activities().unlink()
        self._login_tp()
        _t, tree = self._get(self.player_url)
        self._assert_badge(tree, 'activities', 0, overdue=False)

    # -- UC-2 ------------------------------------------------------------
    def test_player_tab_count_is_per_viewer(self):
        self._activity(self.player, self.tp, days=-3)
        self._login_coach()
        _t, tree = self._get(self.player_url)
        # The therapist's three are not the coach's.
        self._assert_badge(tree, 'activities', 0, overdue=False)
        self._activity(self.player, self.coach, days=1)
        _t, tree = self._get(self.player_url + '&tab=activities')
        self._assert_badge(tree, 'activities', 1, overdue=False)
        self.assertEqual(len(self._panel_rows(tree)), 1)
        self._login_tp()
        _t, tree = self._get(self.player_url + '&tab=activities')
        self._assert_badge(tree, 'activities', 4, overdue=True)
        self.assertEqual(len(self._panel_rows(tree)), 4)

    # -- UC-3 ------------------------------------------------------------
    def test_team_tab_count(self):
        self._login_tp()
        _t, tree = self._get(self.team_url)
        self._assert_badge(tree, 'activities', 1, overdue=False)  # act_team
        self._activity(self.team_a, self.tp, days=-4)
        # A player's activity is not a team activity.
        self._activity(self.player, self.tp, days=-4)
        _t, tree = self._get(self.team_url + '&tab=activities')
        self._assert_badge(tree, 'activities', 2, overdue=True)
        self.assertEqual(len(self._panel_rows(tree)), 2)
        # The coach has none on the team: no pill; then one of their own.
        self._login_coach()
        _t, tree = self._get(self.team_url)
        self._assert_badge(tree, 'activities', 0, overdue=False)
        self._activity(self.team_a, self.coach, days=2)
        _t, tree = self._get(self.team_url)
        self._assert_badge(tree, 'activities', 1, overdue=False)

    # -- UC-4 ------------------------------------------------------------
    def test_other_tabs_and_pages_unchanged(self):
        self._activity(self.player, self.tp, days=-1)
        self._activity(self.team_a, self.tp, days=-1)
        self._login_tp()
        _t, tree = self._get(self.player_url)
        for key in ('injuries', 'info', 'documents', 'notes'):
            tab = self._tab(tree, key)
            if tab is not None:
                self.assertIsNone(self._badge(tab), key)
        _t, tree = self._get(self.team_url)
        for key in ('dashboard', 'players'):
            self.assertIsNone(self._badge(self._tab(tree, key)), key)
        for url in ('/my/activities', '/my/events?no_default_dates=1'):
            _t, tree = self._get(url)
            self.assertTrue(tree.xpath('//nav[@data-sc-tabs]/a'), url)
            self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_tab_badge")]'), url)

    # -- UC-5 ------------------------------------------------------------
    def test_count_follows_completion(self):
        self._login_tp()
        _t, tree = self._get(self.player_url)
        self._assert_badge(tree, 'activities', 2, overdue=False)
        self._player_activities()[:1].action_feedback(feedback='Synthetic done')
        _t, tree = self._get(self.player_url)
        self._assert_badge(tree, 'activities', 1, overdue=False)
        self._activity(self.player, self.tp, days=-2)
        _t, tree = self._get(self.player_url)
        self._assert_badge(tree, 'activities', 2, overdue=True)


@tagged('post_install', '-at_install')
class TestActivityTabCountI18n1635(TabCount1635Mixin, TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    # -- UC-6 ------------------------------------------------------------
    def test_badge_label_in_french(self):
        self._switch(True)
        self._login_tp()
        url = '/my/player?player_id=%s&team_id=%s' % (self.player.id, self.team_a.id)
        tree = lxml_html.fromstring(self._fr(url))
        badge = self._assert_badge(tree, 'activities', 2, overdue=False)
        self.assertEqual(badge.get('aria-label'), '2 activités ouvertes')
        self._activity(self.team_a, self.tp, days=-2)
        tree = lxml_html.fromstring(self._fr('/my/team?team_id=%s' % self.team_a.id))
        badge = self._assert_badge(tree, 'activities', 2, overdue=True)
        self.assertEqual(badge.get('aria-label'), '2 activités ouvertes, dont 1 en retard')
