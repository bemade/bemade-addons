"""Task 1611 — read fragments: the mechanism. Synthetic fixtures only.

Use case: a therapist saves one field in place; every read-only region of the
page that shows something depending on it refreshes without a reload — the
server renders the page as for a reload and answers only the regions asked.

Acceptance criteria:

* AC-F1 Every save answers ``refresh`` (the spec's key patterns resolved for
  the record) and ``saved_at`` (server time, ms); an activity save also
  answers ``live_counts`` (the app bar's overdue badge).
* AC-F2 Every SAVE_REGISTRY spec declares a ``refresh`` map; ``'*'`` resolves
  to every fragment of the record, cross-record entries to the other
  record's keys (an injury -> its player; a timesheet -> its event).
* AC-F3 A page GET with ``X-Sc-Fragments: k1,k2`` answers JSON
  ``{fragments, missing, title, rendered_at}`` (no-store); each fragment is
  byte-identical to that node of a full render; unknown keys are
  ``missing``; malformed keys are ignored.
* AC-F4 A fragment request never pops the pending session notification (it
  stays for the next real page).
* AC-F5 Fragment keys are unique on every shell page, and no fragment holds an
  OWL island (``owl-component``).
* AC-F6 Every shell page carries its server render time
  (``data-sc-rendered-at``, the « back » check).
* AC-F7 The retired ``data-sc-edit-reload`` / ``data-sc-heading`` /
  ``heading`` / ``stage`` paths are gone.
* AC-F8 A coach's fragments follow the coach's page: a hidden injury and the
  therapists-only fields never appear in them.
"""
from collections import Counter

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.app_shell import SAVE_REGISTRY
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon


@tagged('post_install', '-at_install')
class TestFragments1611(FragmentsCommon):

    def _player_url(self, tab='info'):
        return '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)

    # -- AC-F1 -------------------------------------------------------------
    def test_save_answers_refresh_and_saved_at(self):
        self._login_tp()
        payload = self._saved(self.player, 'position', 'Goalie')
        self.assertEqual(payload['refresh'], ['sports.patient:%s:*' % self.player.id])
        self.assertIsInstance(payload['saved_at'], int)
        self.assertNotIn('live_counts', payload)
        payload = self._saved(self.act_player, 'summary', 'Renamed task')
        self.assertTrue(payload['live_counts'])
        self.assertIn('mail.activity:%s:*' % self.act_player.id, payload['refresh'])

    # -- AC-F2 -------------------------------------------------------------
    def test_every_spec_declares_refresh(self):
        for model, spec in SAVE_REGISTRY.items():
            self.assertIn('*', spec.get('refresh') or {}, model)

    def test_cross_record_patterns(self):
        self._login_tp()
        payload = self._saved(self.injury, 'diagnosis', 'Ankle sprain')
        self.assertIn('sports.patient.injury:%s:*' % self.injury.id, payload['refresh'])
        self.assertIn('sports.patient:%s:*' % self.player.id, payload['refresh'])
        self.assertIn('sports.treatment.note:*:meta', payload['refresh'])
        payload = self._saved(self.timesheet, 'coverage_start', '2026-02-02T10:00')
        self.assertIn('sports.event:%s:*' % self.event.id, payload['refresh'])
        self.assertIn('page:timesheets:*', payload['refresh'])
        payload = self._saved(self.event, 'name', 'PC Event renamed')
        self.assertIn('sports.event.timesheet:*:*', payload['refresh'])

    # -- AC-F3 -------------------------------------------------------------
    def test_fragment_answer_is_the_node_of_a_full_render(self):
        self._login_tp()
        url = self._player_url()
        key = 'sports.patient:%s' % self.player.id
        for part in ('appbar', 'crumb', 'hero-head', 'hero-chips', 'allergies', 'hero-actions',
                     'identity', 'memberships', 'removal-sheets'):
            self.assertFragmentMatchesPage(url, '%s:%s' % (key, part))

    def test_missing_and_malformed_keys(self):
        self._login_tp()
        key = 'sports.patient:%s:appbar' % self.player.id
        payload = self._fragments(self._player_url(), [key, 'sports.patient:0:nope', '<script>', ''])
        self.assertEqual(set(payload['fragments']), {key})
        self.assertEqual(payload['missing'], ['sports.patient:0:nope'])
        self.assertIn('One, Pat', payload['title'])
        self.assertIsInstance(payload['rendered_at'], int)

    # -- AC-F4 -------------------------------------------------------------
    def test_fragment_request_keeps_the_session_notification(self):
        self._login_tp()
        # A POST round-trip (« Add to Team ») leaves its notification in the
        # session for the page it redirects to.
        resp = self.url_open('/my/player/%s/add_to_team' % self.player_b.id, data={
            'csrf_token': self._csrf(), 'team_id': self.team_a.id, 'return_url': '/my/players',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self._fragments('/my/players', ['page:none:none'])
        tree = self._page('/my/players')
        toast = tree.xpath('//div[contains(concat(" ", @class, " "), " o_sc_toast ")]')[0]
        self.assertIn('PC Team A', toast.get('data-sc-notify') or '')

    # -- AC-F5 / AC-F6 -----------------------------------------------------
    def _check_page(self, url):
        tree = self._page(url)
        keys = tree.xpath('//*[@data-sc-fragment]/@data-sc-fragment')
        dupes = [key for key, count in Counter(keys).items() if count > 1]
        self.assertFalse(dupes, '%s: duplicate fragment keys %s' % (url, dupes))
        for node in tree.xpath('//*[@data-sc-fragment]'):
            if node.get('data-sc-fragment-mode') == 'list':
                continue
            self.assertFalse(node.xpath('.//owl-component'),
                             '%s: %s holds an OWL island' % (url, node.get('data-sc-fragment')))
        shell = self._shell(tree)
        self.assertTrue(int(shell.get('data-sc-rendered-at')), url)
        return tree

    def test_pages_keys_unique_and_island_free(self):
        self._login_tp()
        for url in (self._player_url('info'), self._player_url('injuries'), self._player_url('notes'),
                    '/my/injury/edit?injury_id=%s' % self.injury.id,
                    '/my/event/%s' % self.event.id,
                    '/my/activity/%s' % self.act_player.id,
                    '/my/sc/timesheets', '/my/notepad', '/my/home', '/my/teams'):
            self._check_page(url)

    # -- AC-F7 -------------------------------------------------------------
    def test_retired_paths(self):
        self._login_tp()
        for url in (self._player_url('info'), self._player_url('injuries'), self._player_url('notes'),
                    '/my/injury/edit?injury_id=%s' % self.injury.id,
                    '/my/event/%s' % self.event.id, '/my/activity/%s' % self.act_player.id,
                    '/my/sc/timesheets', '/my/notepad'):
            text, _tree = self._get(url)
            self.assertNotIn('data-sc-edit-reload', text, url)
            self.assertNotIn('data-sc-heading', text, url)
        payload = self._saved(self.player, 'first_name', 'Pat')
        self.assertNotIn('heading', payload)
        payload = self._saved(self.player, 'sc_status', 'no:no')
        self.assertNotIn('stage', payload)

    # -- AC-F8 -------------------------------------------------------------
    def test_coach_fragments_hide_what_the_coach_page_hides(self):
        hidden = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Hidden synthetic injury',
            'hidden_from_coaches': True,
        })
        self.injury.sudo().write({'internal_notes': 'Synthetic internal note'})
        self.player.sudo().write({'allergies': 'Synthetic allergy'})
        self._login_coach()
        url = self._player_url('injuries')
        key = 'sports.patient:%s' % self.player.id
        payload = self._fragments(url, ['%s:injuries' % key, '%s:allergies' % key,
                                        'sports.patient.injury:%s:read' % self.injury.id,
                                        'sports.patient.injury:%s:summary' % hidden.id])
        blob = ' '.join(payload['fragments'].values())
        self.assertIn('Sprain', blob)
        self.assertNotIn('Hidden synthetic injury', blob)
        self.assertNotIn('Synthetic internal note', blob)
        self.assertNotIn('Synthetic allergy', blob)
        self.assertIn('sports.patient.injury:%s:summary' % hidden.id, payload['missing'])
        # Same as the coach's own page.
        self.assertFragmentMatchesPage(url, '%s:injuries' % key)
