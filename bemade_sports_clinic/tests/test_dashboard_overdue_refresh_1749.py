"""Task 1749 — dashboard « À faire » › « Retours en retard »: a Match pill
change updates the card in place. Synthetic fixtures only (this repository
is public).

Reproduction (2026-11-03, before the fix, scrubbed prod copy, 390 + 1440
px): a « Pratique » change refreshed the overdue card; a « Match » change
to « Oui » saved but the card kept « Match : Non » until a reload — folded
(« Voir les N autres ») or not, and also when the same player is listed in
« Changements récents » (that card refreshed, the overdue one did not).
Cause: the change takes the player OUT of the overdue line (match ≠ Non),
so the fresh render has no card under that key and the page keeps the stale
one (data-pk-fragment-keep, #1634); sc_fill_moved_row_fragments never
applies on the dashboard (its scopes « dash-… » are not ``\\w+`` and the
section that now lists the player is not on the page). Same for « Joueurs
à surveiller »: a change makes the player a recent change, so they leave
that section and its card stayed stale too.

Acceptance criteria:

* UC-1 A visible overdue card: after « Match : Oui » the fragment answer
  carries that card (not ``missing``), fresh (Match « yes »).
* UC-2 A folded overdue card (« Voir les N autres »): same.
* UC-3 A player listed in « Retours en retard » AND « Changements récents »:
  both cards come back fresh.
* UC-4 « Joueurs à surveiller »: a status change (the player becomes a
  recent change) still answers the watch card, fresh.
* UC-5 A change that keeps the player in the line (« Pratique ») refreshes
  the card as before; the full page never renders the kept cards (only a
  fragment request asking for them), and a key for a player the viewer
  cannot read stays ``missing``.
* UC-6 In a browser, phone 390 px and laptop 1440 px: « Match : Oui » on an
  overdue card (visible, folded, and one also in « Changements récents »)
  updates the pill and the dot in place, no reload
  (static/tests/tours/sc_overdue_refresh_1749_tours.js).
"""
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.dashboard_common_1624 import Dashboard1624Common, _player
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsMixin

RETURNS = 'dash-todo-returns'
CHANGES = 'dash-recent_changes'
WATCH = 'dash-watch'


def row_key(player, scope):
    return 'sports.patient:%s:row-%s' % (player.id, scope)


class _Overdue1749:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        today = fields.Date.today()

        def _overdue(player, days):
            player.sudo().with_context(**{PAST_RETURN_OK: True}).write(
                {'predicted_return_date': today - timedelta(days=days)})

        # Order of the line = predicted return date: red first (visible),
        # seven extras (visible), one extra, shared, yellow (folded: 8 shown).
        _overdue(cls.red, 40)
        cls.extras = env['sports.patient']
        for n in range(8):
            extra = _player(env, 'Extra%s' % n, 'Synth', cls.team_a, 'no', 'no')
            _overdue(extra, 30 - n)
            cls.extras |= extra
        _overdue(cls.shared, 4)
        _overdue(cls.yellow, 3)
        env.flush_all()
        # « Changements récents »: shared only (the others' stamps cleared).
        others = (cls.red | cls.yellow | cls.extras | cls.player_b | cls.player)
        env.cr.execute(
            "UPDATE sports_patient SET dashboard_last_activity_tp = NULL,"
            " dashboard_last_activity_coach = NULL WHERE id IN %s", [tuple(others.ids)])
        env.invalidate_all()

    @contextmanager
    def _shared_changed(self):
        """« Shared Synth » counts as a recent change (its stamp is kept;
        the presence rule — tracked net changes — is extended with it), on
        top of whatever a save in the test makes a change."""
        Patient = type(self.env['sports.patient'])
        original = Patient._dashboard_card_presence
        shared_id = self.shared.id

        def presence(recs, patients, role, cutoff=None):
            result = original(recs, patients, role, cutoff)
            if shared_id in patients.ids:
                result['players'] = set(result['players']) | {shared_id}
            return result

        with patch.object(Patient, '_dashboard_card_presence', presence):
            yield


@tagged('post_install', '-at_install')
class TestOverdueRefresh1749(_Overdue1749, FragmentsMixin, Dashboard1624Common):

    def setUp(self):
        super().setUp()
        self.enterContext(self._shared_changed())

    def _home(self):
        _text, tree = self._get('/my/home')
        return tree

    def _match_value(self, html):
        node = lxml_html.fragment_fromstring(html)
        return node.xpath('.//*[@data-sc-pill-key="match"]/button/@data-sc-pill-value')[0]

    def _fresh(self, keys):
        answer = self._fragments('/my/home', keys)
        for key in keys:
            self.assertIn(key, answer['fragments'], 'stale: %s missing (%s)' % (key, answer['missing']))
        return answer

    def test_fixture_shape(self):
        """The case the bug needs: red visible, shared + yellow folded, shared
        also in « Changements récents », red + yellow in « À surveiller »."""
        self._login_tp()
        tree = self._home()
        line = self._section(tree, 'todo').xpath('.//details[@data-sc-todo="returns"]')[0]
        folded = line.xpath('.//details[@data-sc-dw-more]')[0]
        self.assertTrue(folded.xpath('.//*[@data-pk-fragment="%s"]' % row_key(self.shared, RETURNS)))
        self.assertTrue(folded.xpath('.//*[@data-pk-fragment="%s"]' % row_key(self.yellow, RETURNS)))
        self.assertFalse(folded.xpath('.//*[@data-pk-fragment="%s"]' % row_key(self.red, RETURNS)))
        self.assertTrue(line.xpath('.//*[@data-pk-fragment="%s"]' % row_key(self.red, RETURNS)))
        self.assertTrue(tree.xpath('//*[@data-pk-fragment="%s"]' % row_key(self.shared, CHANGES)))
        self.assertTrue(tree.xpath('//*[@data-pk-fragment="%s"]' % row_key(self.red, WATCH)))

    # -- UC-1 ---------------------------------------------------------------
    def test_visible_card_follows_match_change(self):
        self._login_tp()
        self._home()
        payload = self._saved(self.red, 'sc_status', 'yes:yes')
        self.assertRefreshes(payload, row_key(self.red, RETURNS))
        answer = self._fresh([row_key(self.red, RETURNS)])
        self.assertEqual(self._match_value(answer['fragments'][row_key(self.red, RETURNS)]), 'yes')

    # -- UC-2 ---------------------------------------------------------------
    def test_folded_card_follows_match_change(self):
        self._login_tp()
        self._home()
        self._saved(self.yellow, 'sc_status', 'yes:yes')
        answer = self._fresh([row_key(self.yellow, RETURNS)])
        self.assertEqual(self._match_value(answer['fragments'][row_key(self.yellow, RETURNS)]), 'yes')

    # -- UC-3 ---------------------------------------------------------------
    def test_player_in_two_sections(self):
        self._login_tp()
        self._home()
        self._saved(self.shared, 'sc_status', 'yes:yes')
        keys = [row_key(self.shared, RETURNS), row_key(self.shared, CHANGES)]
        answer = self._fresh(keys)
        for key in keys:
            self.assertEqual(self._match_value(answer['fragments'][key]), 'yes', key)
            # Each card keeps its own scope (key, menu ids, detail region).
            self.assertIn('data-pk-fragment="%s"' % key, answer['fragments'][key])
        self.assertNotIn('-%s"' % CHANGES, answer['fragments'][keys[0]])

    # -- UC-4 ---------------------------------------------------------------
    def test_watch_card_follows_a_change(self):
        self._login_tp()
        self._home()
        self._saved(self.red, 'sc_status', 'no:yes')
        answer = self._fresh([row_key(self.red, WATCH), row_key(self.red, RETURNS)])
        for key in (row_key(self.red, WATCH), row_key(self.red, RETURNS)):
            node = lxml_html.fragment_fromstring(answer['fragments'][key])
            self.assertEqual(node.xpath('.//*[@data-sc-pill-key="practice"]/button/@data-sc-pill-value'),
                             ['yes'], key)

    # -- UC-5 ---------------------------------------------------------------
    def test_practice_change_and_no_kept_cards_on_the_page(self):
        self._login_tp()
        self._saved(self.red, 'sc_status', 'no:yes')
        tree = self._home()
        # Still overdue: listed in the line as before.
        line = self._section(tree, 'todo').xpath('.//details[@data-sc-todo="returns"]')[0]
        self.assertTrue(line.xpath('.//*[@data-pk-fragment="%s"]' % row_key(self.red, RETURNS)))
        self._saved(self.red, 'sc_status', 'yes:yes')
        tree = self._home()
        self.assertFalse(tree.xpath('//*[@data-pk-fragment="%s"]' % row_key(self.red, RETURNS)),
                         'a full render never carries a card its section dropped')
        self.assertFalse(tree.xpath('//*[@data-sc-dash-kept]'))

    def test_unreadable_player_stays_missing(self):
        """Pat Two (Team B: nobody of ours) is not readable by the therapist:
        a forged key for them never renders a card."""
        self._login_tp()
        key = row_key(self.player_b, RETURNS)
        answer = self._fragments('/my/home', [key])
        self.assertEqual(answer['missing'], [key])


class _Tour1749(_Overdue1749, Dashboard1624Common):

    def _run(self):
        self.enterContext(self._shared_changed())
        self.start_tour('/my/home', 'sc_1749_overdue_refresh', login='pc.tp@example.com')
        for player in (self.red, self.yellow, self.shared):
            self.assertEqual((player.match_status, player.practice_status), ('yes', 'yes'), player.name)


@tagged('post_install', '-at_install')
class TestOverdueRefreshTourPhone1749(_Tour1749):
    browser_size = '390x844'

    def test_overdue_refresh_tour_phone(self):
        self._run()


@tagged('post_install', '-at_install')
class TestOverdueRefreshTourLaptop1749(_Tour1749):
    browser_size = '1440x900'

    def test_overdue_refresh_tour_laptop(self):
        self._run()
