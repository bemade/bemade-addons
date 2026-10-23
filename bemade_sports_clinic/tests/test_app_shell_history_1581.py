"""Task 1581 — one pattern for every history of the portal app shell.
Synthetic fixtures only.

The standard is the training-recommendation history: a green « History »
link next to the field label / in the section header opens the shared sheet,
whose body is fetched on EVERY open (lazy + fresh), always present with an
empty state, every entry in ONE format.

Acceptance criteria covered here (the in-browser « fresh on every open » is
in test_app_shell_tours_1581.py):

* UC-H1 Shared entry (``sc_history_entry``): « <date> <time> · <Full Name> ·
  <action chip> » then the body, the date-time in the treatment notes' format
  (« d MMM y HH:mm », viewer's tz); an empty body reads « Cleared »; an
  archived announcement carries the « Archived » chip and state.
* UC-H2 Empty states: each history fragment says so when there is nothing.
* UC-H3 Triggers: the team announcement, the training recommendation and the
  injury notes each have a green link (``o_sc_link_btn``) opening a sheet
  with ``data-sc-lazy-url`` + ``data-sc-lazy-fresh``; the announcement history
  is no longer rendered with the page; the injury page's « Note History »
  button is gone.
* UC-H4 Role gating: the announcement fragment answers the team's staff only
  (another team / a plain portal user → 403); the injury-notes fragment
  follows the injury's access — a therapist gets internal + external rows, a
  coach external rows only (even with ``?scope=internal``) and a 403 for an
  injury hidden from coaches.
* UC-H5 Injury notes: « All / Internal / External » chips INSIDE the sheet
  (therapists only) re-fetch the fragment with ``?scope=``.
* UC-H6 The notes-history page is retired in the shell: it redirects to the
  injury page (same context); switch off, the legacy page is unchanged.
* UC-H7 Daily digests: the team page's « History » opens the digest list page
  (back chain covered by test_app_shell_nav_1579 / its tours).
* UC-H8 French: entries, chips and empty states render in fr_CA.
"""
import re
from datetime import datetime

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common

# « 3 mars 2026 14:05 » / « Mar 3, 2026 … » never: d MMM y HH:mm.
WHEN_RE = re.compile(r'^\d{1,2} \S+ \d{4} \d{2}:\d{2}$')


class History1581Common(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.team_url = '/my/team?team_id=%s' % cls.team_a.id
        Hist = env['sports.team.note.history'].sudo()
        cls.ann_posted = Hist.create({
            'team_id': cls.team_a.id, 'author_id': cls.tp.id, 'action': 'set',
            'body': 'Synthetic announcement one',
            'note_datetime': datetime(2026, 3, 3, 14, 5),
        })
        cls.ann_archived = Hist.create({
            'team_id': cls.team_a.id, 'author_id': cls.tp.id, 'action': 'dismiss',
            'body': 'Synthetic announcement one',
            'note_datetime': datetime(2026, 3, 4, 9, 30),
        })
        Notes = env['sports.injury.note.history'].sudo()
        cls.note_ext = Notes.create({
            'injury_id': cls.injury.id, 'patient_id': cls.player.id, 'author_id': cls.tp.id,
            'scope': 'external', 'content': 'Synthetic external snapshot',
            'note_datetime': datetime(2026, 3, 5, 10, 0),
        })
        cls.note_int = Notes.create({
            'injury_id': cls.injury.id, 'patient_id': cls.player.id, 'author_id': cls.tp.id,
            'scope': 'internal', 'content': 'Synthetic internal snapshot',
            'note_datetime': datetime(2026, 3, 6, 10, 0),
        })
        cls.note_cleared = Notes.create({
            'injury_id': cls.injury.id, 'patient_id': cls.player.id, 'author_id': cls.tp.id,
            'scope': 'external', 'content': '',
            'note_datetime': datetime(2026, 3, 7, 10, 0),
        })
        cls.hidden_injury = env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic hidden injury',
            'hidden_from_coaches': True,
        })
        Notes.create({
            'injury_id': cls.hidden_injury.id, 'patient_id': cls.player.id,
            'author_id': cls.tp.id, 'scope': 'external',
            'content': 'Synthetic hidden external snapshot',
        })
        cls.notes_url = '/my/injury/%s/notes/history/fragment' % cls.injury.id
        cls.ann_url = '/my/team/%s/announcement/history' % cls.team_a.id

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _fragment(self, url, status=200):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, status, url)
        return lxml_html.fromstring(resp.text or '<p/>')

    @staticmethod
    def _entries(tree):
        out = []
        for li in tree.xpath('//li[contains(concat(" ", @class, " "), " o_sc_history_entry ")]'):
            out.append({
                'when': ''.join(li.xpath('.//*[contains(@class, "o_sc_history_when")]//text()')).strip(),
                'author': ''.join(li.xpath('.//*[contains(@class, "o_sc_history_author")]//text()')).strip(),
                'chips': [c.text_content().strip() for c in li.xpath('.//*[contains(@class, "o_sc_chip")]')],
                'body': ''.join(li.xpath('.//*[contains(@class, "o_sc_history_body")]//text()')).strip(),
                'state': li.get('data-sc-history-state'),
                'text': ' '.join(li.text_content().split()),
                'scope': li.get('data-sc-scope'),
            })
        return out


@tagged('post_install', '-at_install')
class TestAppShellHistory1581(History1581Common):

    # -- UC-H1 -----------------------------------------------------------
    def test_announcement_entries_share_the_format(self):
        self._login_coach()
        entries = self._entries(self._fragment(self.ann_url))
        self.assertEqual(len(entries), 2)
        archived, posted = entries  # newest first
        for entry in entries:
            self.assertRegex(entry['when'], WHEN_RE)
            self.assertEqual(entry['author'], 'PC TP')
            self.assertEqual(entry['body'], 'Synthetic announcement one')
        self.assertEqual(posted['chips'], ['Posted'])
        self.assertEqual(archived['chips'], ['Archived'])
        self.assertEqual(archived['state'], 'archived')

    def _save_training(self, value):
        self.player.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'training_recommendation', 'value': value,
            'write_date': fields.Datetime.to_string(self.player.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_training_entries_share_the_format(self):
        self._login_tp()
        self._save_training('Synthetic bike only')
        self._save_training('')
        entries = self._entries(self._fragment('/my/player/%s/training-history' % self.player.id))
        self.assertEqual(len(entries), 2)
        cleared, set_ = entries
        self.assertRegex(set_['when'], WHEN_RE)
        self.assertEqual(set_['author'], 'PC TP')
        self.assertEqual(set_['body'], 'Synthetic bike only')
        self.assertEqual(cleared['state'], 'cleared')
        self.assertIn('Cleared', cleared['text'])

    def test_note_entries_share_the_format(self):
        self._login_tp()
        entries = self._entries(self._fragment(self.notes_url))
        self.assertEqual([e['scope'] for e in entries], ['external', 'internal', 'external'])
        cleared, internal, external = entries
        self.assertRegex(internal['when'], WHEN_RE)
        self.assertEqual(internal['author'], 'PC TP')
        self.assertEqual(internal['chips'], ['Internal'])
        self.assertEqual(internal['body'], 'Synthetic internal snapshot')
        self.assertEqual(external['chips'], ['External'])
        self.assertEqual(cleared['state'], 'cleared')
        self.assertIn('Cleared', cleared['text'])

    # -- UC-H2 -----------------------------------------------------------
    def test_empty_states(self):
        # A team the therapist staffs without any announcement history, and
        # an injury without note history.
        self.env['sports.team.staff'].create({
            'team_id': self.team_b.id, 'partner_id': self.tp.partner_id.id, 'role': 'therapist'})
        self.env['sports.injury.note.history'].sudo().search(
            [('injury_id', '=', self.hidden_injury.id)]).unlink()
        self._login_tp()
        for url, message in (
                ('/my/team/%s/announcement/history' % self.team_b.id, 'No announcement history yet.'),
                ('/my/player/%s/training-history' % self.player.id,
                 'No training recommendation history yet.'),
                ('/my/injury/%s/notes/history/fragment' % self.hidden_injury.id,
                 'No note history yet.')):
            tree = self._fragment(url)
            self.assertFalse(self._entries(tree), url)
            self.assertEqual(tree.xpath('//*[contains(@class, "o_sc_empty")]/text()'), [message], url)

    # -- UC-H3 -----------------------------------------------------------
    def _sheet(self, tree, sheet_id):
        sheet = tree.xpath('//dialog[@id="%s"]' % sheet_id)
        self.assertEqual(len(sheet), 1, sheet_id)
        return sheet[0]

    def test_announcement_trigger_and_lazy_fresh_sheet(self):
        self._login_tp()
        _text, tree = self._get(self.team_url)
        link = tree.xpath('//*[@data-sc-section="team.announcement.area"]'
                          '//*[contains(@class, "o_sc_section_header")]'
                          '//*[@data-sc-sheet-open="sc_announcement_history_sheet"]')
        self.assertEqual(len(link), 1)
        self.assertIn('o_sc_link_btn', link[0].get('class'))
        sheet = self._sheet(tree, 'sc_announcement_history_sheet')
        self.assertEqual(sheet.get('data-sc-lazy-url'), self.ann_url)
        self.assertEqual(sheet.get('data-sc-lazy-fresh'), '1')
        self.assertNotIn('Synthetic announcement one', sheet.text_content())

    def test_injury_notes_trigger_and_lazy_fresh_sheet(self):
        self._login_tp()
        _text, tree = self._get('/my/injury/edit?injury_id=%s&team_id=%s' % (self.injury.id, self.team_a.id))
        self.assertFalse(tree.xpath('//*[@data-sc-action="injury.history"]'))
        # Task 1616: the injury page is the open card (its own sheet ids).
        sheet = self._sheet(tree, 'sc_note_history_sheet_%s' % self.injury.id)
        self.assertEqual(sheet.get('data-sc-lazy-url'), self.notes_url)
        self.assertEqual(sheet.get('data-sc-lazy-fresh'), '1')
        # Pencil paradigm (owner review 2026-10-11): ONE « History » link in
        # the notes card's head, reachable while reading.
        links = tree.xpath('//details[@id="injury-%s"]//*[@data-sc-edit-card="injury-notes"]'
                           '/*[contains(@class, "o_sc_edit_card_head")]'
                           '//*[@data-sc-sheet-open="sc_note_history_sheet_%s"][contains(@class, "o_sc_link_btn")]'
                           % (self.injury.id, self.injury.id))
        self.assertEqual(len(links), 1)

    def test_training_trigger_and_lazy_fresh_sheet(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&tab=info' % self.player.id)
        sheet = self._sheet(tree, 'sc_training_history_sheet')
        self.assertEqual(sheet.get('data-sc-lazy-fresh'), '1')

    # -- UC-H4 -----------------------------------------------------------
    @mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.team_management_portal')
    def test_announcement_fragment_role_gated(self):
        self._login_coach()
        self._fragment('/my/team/%s/announcement/history' % self.team_b.id, status=403)
        self._login_plain()
        self._fragment(self.ann_url, status=403)

    @mute_logger('odoo.http', 'odoo.addons.bemade_sports_clinic.controllers.patient_injury_portal')
    def test_notes_fragment_role_gated(self):
        self._login_coach()
        for url in (self.notes_url, self.notes_url + '?scope=internal', self.notes_url + '?scope=all'):
            entries = self._entries(self._fragment(url))
            self.assertEqual({e['scope'] for e in entries}, {'external'}, url)
            self.assertNotIn('Synthetic internal snapshot', ' '.join(e['text'] for e in entries))
        # An injury hidden from coaches: refused outright (its record rule).
        tree = self._fragment('/my/injury/%s/notes/history/fragment' % self.hidden_injury.id,
                              status=403)
        self.assertNotIn('Synthetic hidden external snapshot', tree.text_content())
        self._login_plain()
        self._fragment(self.notes_url, status=403)
        # Another team's injury: refused like the injury page.
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player_c.id, 'diagnosis': 'Synthetic other team'})
        self._login_tp()
        self._fragment('/my/injury/%s/notes/history/fragment' % other.id, status=403)

    # -- UC-H5 -----------------------------------------------------------
    def test_scope_chips_inside_the_sheet(self):
        self._login_tp()
        tree = self._fragment(self.notes_url)
        chips = tree.xpath('//nav[@data-sc-section="history.scope"]//a[@data-sc-sheet-refetch]')
        self.assertEqual([c.get('href') for c in chips],
                         [self.notes_url + '?scope=%s' % s for s in ('all', 'internal', 'external')])
        self.assertEqual([c.get('aria-pressed') for c in chips], ['true', 'false', 'false'])
        tree = self._fragment(self.notes_url + '?scope=internal')
        self.assertEqual([e['scope'] for e in self._entries(tree)], ['internal'])
        self.assertEqual(tree.xpath('//nav[@data-sc-section="history.scope"]//a[@aria-pressed="true"]/@href'),
                         [self.notes_url + '?scope=internal'])
        self._login_coach()
        self.assertFalse(self._fragment(self.notes_url).xpath('//nav[@data-sc-section="history.scope"]'))

    # -- UC-H6 -----------------------------------------------------------
    def test_notes_history_page_retired_in_the_shell(self):
        self._login_tp()
        resp = self.url_open('/my/injury/%s/notes/history?team_id=%s' % (self.injury.id, self.team_a.id),
                             allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        # Task 1616: … the open injury card (team context kept).
        self.assertIn('/my/player?player_id=%s&team_id=%s&tab=injuries&injury=%s#injury-%s' % (
            self.player.id, self.team_a.id, self.injury.id, self.injury.id), resp.headers['Location'])
        self._switch(False)
        resp = self.url_open('/my/injury/%s/notes/history' % self.injury.id)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('data-sc-app-shell', resp.text)

    # -- UC-H7 -----------------------------------------------------------
    def test_digest_history_link_goes_to_the_list(self):
        self._login_tp()
        _text, tree = self._get(self.team_url)
        self.assertEqual(tree.xpath('//a[@data-sc-action="team.digest_history"]/@href'),
                         ['/my/team/%s/digest-history' % self.team_a.id])
        self.assertFalse(tree.xpath('//dialog[@id="sc_digest_history_sheet"]'))


@tagged('post_install', '-at_install')
class TestAppShellHistoryFr1581(TestAppShellI18n1538):

    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['sports.team.note.history'].sudo().create({
            'team_id': cls.team_a.id, 'author_id': cls.tp.id, 'action': 'set',
            'body': 'Synthetic announcement fr'})
        cls.env['sports.injury.note.history'].sudo().create({
            'injury_id': cls.injury.id, 'patient_id': cls.player.id, 'author_id': cls.tp.id,
            'scope': 'internal', 'content': ''})

    def test_histories_in_french(self):
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/team/%s/announcement/history' % self.team_a.id)
        self.assertIn('Publiée', text)
        text = self._fr('/my/injury/%s/notes/history/fragment' % self.injury.id)
        for term in ('Toutes', 'Internes', 'Externes', 'Interne', 'Effacée'):
            self.assertIn(term, text, term)
        text = self._fr('/my/team?team_id=%s' % self.team_a.id).replace('&#39;', "'")
        for term in ('Historique des annonces', 'Chargement…'):
            self.assertIn(term, text, term)
        text = self._fr('/my/injury/edit?injury_id=%s' % self.injury.id)
        self.assertIn('Historique des notes', text)
