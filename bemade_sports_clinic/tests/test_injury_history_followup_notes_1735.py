"""Task 1735 — an injury's « Note history » sheet also lists the player's
Notes-tab notes (``sports.treatment.note``) linked to that injury, for
therapists. Synthetic fixtures only (this repository is public).

Acceptance criteria:

* UC-1 A therapist (portal or internal) sees the injury's linked treatment
  notes under « All » and « Internal », never under « External »; each one
  carries a « Follow-up note » chip (tone distinct from Internal / External),
  its author and its text, and counts as an internal entry
  (``data-sc-scope="internal"``).
* UC-2 A treatment note linked to ANOTHER injury, or to no injury, is absent.
* UC-3 A coach never sees treatment notes, whatever ``?scope=`` says (the
  coach holds no treatment-note ACL: the controller never queries them).
* UC-4 A deleted treatment note is gone from the sheet on the next open.
* UC-5 Both sources are merged newest first: a note written the day of its
  date sorts at its write time; a back-dated note sorts at the end of its date.
* UC-6 The empty state shows only when both sources are empty.
* UC-7 French: « Note de suivi ».
"""
from datetime import date, datetime

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_history_1581 import History1581Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


@tagged('post_install', '-at_install')
class TestInjuryHistoryFollowupNotes1735(History1581Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Notes = cls.env['sports.treatment.note'].sudo()
        # Back-dated: written today, dated 2026-03-05 → sorts at the end of
        # that day (after the 10:00 external snapshot, before 03-06).
        cls.followup = Notes.create({
            'patient_id': cls.player.id, 'injury_id': cls.injury.id,
            'user_id': cls.tp.id, 'date': date(2026, 3, 5),
            'note': 'Synthetic follow-up on the injury',
        })
        cls.other_injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic other injury'})
        Notes.create({
            'patient_id': cls.player.id, 'injury_id': cls.other_injury.id,
            'user_id': cls.tp.id, 'date': date(2026, 3, 5),
            'note': 'Synthetic note on the other injury',
        })
        Notes.create({
            'patient_id': cls.player.id, 'user_id': cls.tp.id,
            'date': date(2026, 3, 5), 'note': 'Synthetic general note',
        })

    def _bodies(self, url):
        return [e['body'] for e in self._entries(self._fragment(url))]

    # -- UC-1 / UC-2 / UC-5 ------------------------------------------------
    def test_therapist_sees_linked_followup_notes_merged(self):
        for login in (self._login_tp, self._login_itp):
            login()
            entries = self._entries(self._fragment(self.notes_url))
            self.assertEqual(
                [e['body'] for e in entries],
                ['', 'Synthetic internal snapshot', 'Synthetic follow-up on the injury',
                 'Synthetic external snapshot'], login.__name__)
            followup = entries[2]
            self.assertEqual(followup['chips'], ['Follow-up note'])
            self.assertEqual(followup['author'], 'PC TP')
            self.assertEqual(followup['scope'], 'internal')
            self.assertTrue(followup['when'])
            self.assertNotIn('Synthetic note on the other injury', ' '.join(e['text'] for e in entries))
            self.assertNotIn('Synthetic general note', ' '.join(e['text'] for e in entries))

    def test_followup_chip_tone_is_distinct(self):
        self._login_tp()
        tree = self._fragment(self.notes_url)
        classes = {chip.text_content().strip(): chip.get('class')
                   for chip in tree.xpath('//li//*[contains(@class, "o_sc_chip")]')}
        self.assertIn('o_sc_chip_green', classes['Follow-up note'])
        self.assertNotEqual(classes['Follow-up note'], classes['Internal'])
        self.assertNotEqual(classes['Follow-up note'], classes['External'])

    def test_scope_filters(self):
        self._login_tp()
        self.assertEqual(self._bodies(self.notes_url + '?scope=internal'),
                         ['Synthetic internal snapshot', 'Synthetic follow-up on the injury'])
        external = self._bodies(self.notes_url + '?scope=external')
        self.assertNotIn('Synthetic follow-up on the injury', external)
        self.assertEqual(external, ['', 'Synthetic external snapshot'])

    def test_same_day_note_sorts_at_its_write_time(self):
        today_note = self.env['sports.treatment.note'].sudo().create({
            'patient_id': self.player.id, 'injury_id': self.injury.id,
            'user_id': self.tp.id, 'note': 'Synthetic note written today',
        })
        self.assertEqual(today_note.date, fields.Date.context_today(today_note))
        self._login_tp()
        self.assertEqual(self._bodies(self.notes_url)[0], 'Synthetic note written today')

    # -- UC-3 --------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_coach_never_sees_followup_notes(self):
        self._login_coach()
        for url in (self.notes_url, self.notes_url + '?scope=internal', self.notes_url + '?scope=all'):
            tree = self._fragment(url)
            self.assertNotIn('Synthetic follow-up on the injury', tree.text_content(), url)
            self.assertNotIn('Follow-up note', tree.text_content(), url)

    # -- UC-4 --------------------------------------------------------------
    def test_deleted_note_is_gone(self):
        self._login_tp()
        self.assertIn('Synthetic follow-up on the injury', self._bodies(self.notes_url))
        self.followup.sudo().unlink()
        self.assertNotIn('Synthetic follow-up on the injury', self._bodies(self.notes_url))

    # -- UC-6 --------------------------------------------------------------
    def test_empty_state_only_when_both_sources_empty(self):
        self.env['sports.injury.note.history'].sudo().search(
            [('injury_id', '=', self.other_injury.id)]).unlink()
        url = '/my/injury/%s/notes/history/fragment' % self.other_injury.id
        self._login_tp()
        tree = self._fragment(url)
        self.assertEqual([e['body'] for e in self._entries(tree)], ['Synthetic note on the other injury'])
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_empty")]'))
        self.env['sports.treatment.note'].sudo().search(
            [('injury_id', '=', self.other_injury.id)]).unlink()
        tree = self._fragment(url)
        self.assertFalse(self._entries(tree))
        self.assertEqual(tree.xpath('//*[contains(@class, "o_sc_empty")]/text()'), ['No note history yet.'])


@tagged('post_install', '-at_install')
class TestInjuryHistoryFollowupNotesFr1735(TestAppShellI18n1538):

    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_followup_chip_in_french(self):
        self.env['sports.treatment.note'].sudo().create({
            'patient_id': self.player.id, 'injury_id': self.injury.id,
            'user_id': self.tp.id, 'date': date(2026, 3, 5),
            'note': 'Synthetic follow-up fr',
        })
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/injury/%s/notes/history/fragment' % self.injury.id)
        self.assertIn('Synthetic follow-up fr', text)
        self.assertIn('Note de suivi', text)
