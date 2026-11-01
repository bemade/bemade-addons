"""Task 1583 — the session notification (``request.session['notification']``,
set by the POST round-trips such as « Ajouter à l'équipe ») is shown on the
NEXT app shell page, whatever it is, as the status toast. Synthetic fixtures.

Acceptance criteria covered here:

* UC-T1 Adding a player to a team from the players list shows the
  confirmation on that list, once: the toast host carries the message on the
  redirected page and not on the next one.
* UC-T2 An error from the same route (team the user does not staff) shows on
  the list too, with the error tone.
* UC-T3 The team page still shows a pending message — once, as the toast (its
  own banner block is gone, nothing shows twice).
* UC-T4 Switch OFF: the legacy pages are unchanged (no toast host; the
  legacy team-players page keeps its alert).
* UC-T5 fr_CA (website-aware): the confirmation and the error read in
  French.
"""
from lxml import html as lxml_html

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class SessionToastCommon1583(AppShellCommon):

    @staticmethod
    def _notify(tree):
        """(message, title, tone) carried by the toast host, or None."""
        hosts = tree.xpath('//div[contains(concat(" ", @class, " "), " o_sc_toast ")]')
        if not hosts or not hosts[0].get('data-sc-notify'):
            return None
        host = hosts[0]
        return (host.get('data-sc-notify'), host.get('data-sc-notify-title'),
                host.get('data-sc-notify-tone'))

    def _add_to_team(self, player, team, return_url):
        resp = self.url_open('/my/player/%s/add_to_team' % player.id, data={
            'csrf_token': self._csrf(), 'team_id': team.id, 'return_url': return_url,
        })
        self.assertEqual(resp.status_code, 200)
        return resp.text, lxml_html.fromstring(resp.text)


@tagged('post_install', '-at_install')
class TestAppShellSessionToast1583(SessionToastCommon1583):

    def test_add_to_team_confirmed_on_list_once(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._add_to_team(self.player_b, self.team_a, '/my/players?last_name=Two')
        self.assertIsNotNone(self._shell(tree))
        notify = self._notify(tree)
        self.assertTrue(notify, 'the list must carry the confirmation')
        message, title, tone = notify
        self.assertIn('Two', message)
        self.assertIn('PC Team A', message)
        self.assertEqual(tone, 'success')
        self.assertTrue(title)
        # The row is now a link to the player.
        self.assertTrue(tree.xpath('//a[@href="/my/player?player_id=%s"]' % self.player_b.id))
        # Popped: the next page shows nothing.
        _text, tree = self._get('/my/players?last_name=Two')
        self.assertIsNone(self._notify(tree))

    def test_add_to_team_error_on_list(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._add_to_team(self.player, self.team_b, '/my/players')
        message, _title, tone = self._notify(tree)
        self.assertIn('team you staff', message)
        self.assertEqual(tone, 'error')
        _text, tree = self._get('/my/players')
        self.assertIsNone(self._notify(tree))

    def test_team_page_shows_pending_message_once(self):
        self._switch(True)
        self._login_tp()
        team_url = '/my/team?team_id=%s' % self.team_a.id
        text, tree = self._add_to_team(self.player_b, self.team_a, team_url)
        self.assertIsNotNone(self._shell(tree))
        message, _title, _tone = self._notify(tree)
        self.assertIn('Two', message)
        # Once: the toast only, no banner repeating it.
        self.assertEqual(text.count('has been added to'), 1)
        _text, tree = self._get(team_url)
        self.assertIsNone(self._notify(tree))

    def test_switch_off_legacy_unchanged(self):
        self._login_tp()
        text, tree = self._add_to_team(self.player_b, self.team_a, '/my/players')
        self.assertIsNone(self._shell(tree))
        self.assertNotIn('data-sc-notify', text)


@tagged('post_install', '-at_install')
class TestAppShellToastTourPhone1583(SessionToastCommon1583):
    """UC-T1 in a browser (static/tests/tours/sc_app_toast_tours.js)."""
    browser_size = '390x844'

    def test_add_to_team_toast(self):
        self._switch(True)
        self.start_tour('/my/players?last_name=Two', 'sc_1583_add_to_team_toast',
                        login='pc.tp@example.com')
        self.player_b.invalidate_recordset(['team_ids'])
        self.assertIn(self.team_a, self.player_b.team_ids)


@tagged('post_install', '-at_install')
class TestAppShellSessionToastFr1583(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None

    _notify = staticmethod(SessionToastCommon1583._notify)

    def _add_fr(self, player, team, return_url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        csrf = self._csrf()
        resp = self.url_open('/my/player/%s/add_to_team' % player.id, data={
            'csrf_token': csrf, 'team_id': team.id, 'return_url': return_url,
        })
        self.assertEqual(resp.status_code, 200)
        return lxml_html.fromstring(resp.text)

    def test_toast_in_french(self):
        self._switch(True)
        self._login_tp()
        message, title, _tone = self._notify(self._add_fr(self.player_b, self.team_a, '/my/players'))
        self.assertIn('a été ajouté à PC Team A', message)
        self.assertEqual(title, 'Joueur ajouté')
        message, title, _tone = self._notify(self._add_fr(self.player, self.team_b, '/my/players'))
        self.assertIn('Vous pouvez seulement ajouter des joueurs', message)
        self.assertEqual(title, 'Accès refusé')
