"""Task 1539 — the P2 entries of the server autosave registry
(POST /my/app/save/<model>/<id>). Synthetic fixtures only.

Acceptance criteria covered here (AC3 / AC5):

* UC-R1 Per-role allowlists are enforced SERVER-SIDE: a coach posting a
  therapist-only field (player allergies, the status pair, injury stage /
  internal notes / visibility / predicted date) gets 403 and nothing is
  written, although the ORM would let a coach write the injury.
* UC-R2 A blur save writes ONE field and adds exactly ONE note-history row
  (external notes); a stale ``write_date`` answers 409 and writes nothing.
* UC-R3 Match / practice status are saved as a PAIR in one save; an invalid
  pair answers 400 and writes nothing.
* UC-R4 Coach rename (#1537) through the save route (a blank name is
  refused); jersey normalisation (#1421) and the duplicate warning surfaced
  as the field's inline message.
* UC-R5 Injury rules: a coach rewords an UNVERIFIED injury only; « Résoudre »
  stores the stage and the resolution date together; the date and its N/A
  box are one value.
* UC-R6 Treatment note edit (sudo hook): the author may, another therapist
  may not (403), a coach may not (403); the model guard still applies.
* UC-R7 The primary emergency contact is editable by a coach.
* UC-R8 A sudo_write spec without a permission callable is refused at
  registry validation.
"""
from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers import app_shell
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellSave1539(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T1539 Second TP', 'login': 't1539.tp2@example.com',
            'password': 't1539-tp2-pass', 'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id,
            'role': 'therapist',
        })
        cls.note = env['sports.treatment.note'].create({
            'patient_id': cls.player.id, 'note': 'Synthetic note', 'user_id': cls.tp.id,
            'date': '2026-01-10',
        })
        cls.mate = env['sports.patient'].create({
            'first_name': 'Mate', 'last_name': 'Synthetic', 'jersey_number': '12',
            'team_ids': [Command.set([cls.team_a.id])],
        })

    # ---------------------------------------------------------------- utils
    def _wd(self, record):
        record.invalidate_recordset()
        return fields.Datetime.to_string(record.write_date)

    def _save(self, record, field, value, write_date=None):
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value,
            'write_date': write_date or self._wd(record),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _history_count(self, injury):
        return self.env['sports.injury.note.history'].search_count(
            [('injury_id', '=', injury.id)])

    # -- UC-R1 -----------------------------------------------------------
    def test_coach_refused_therapist_fields(self):
        self._login_coach()
        self.player.sudo().write({'allergies': 'Peanuts'})
        for field, value in (('allergies', 'None'), ('sc_status', 'no:no'),
                             ('training_recommendation', 'Rest'),
                             ('team_info_notes', 'x'), ('date_of_birth', '2010-01-01')):
            resp = self._save(self.player, field, value)
            self.assertEqual(resp.status_code, 403, field)
        for field, value in (('stage', 'resolved'), ('internal_notes', 'Coach text'),
                             ('hidden_from_coaches', '1'),
                             ('predicted_resolution_date', '2030-01-01'),
                             ('parental_consent', 'yes')):
            resp = self._save(self.injury, field, value)
            self.assertEqual(resp.status_code, 403, field)
        self.player.invalidate_recordset()
        self.injury.invalidate_recordset()
        self.assertEqual(self.player.sudo().allergies, 'Peanuts')
        self.assertEqual(self.player.match_status, 'yes')
        self.assertEqual(self.injury.stage, 'active')
        self.assertFalse(self.injury.sudo().internal_notes)
        self.assertFalse(self.injury.hidden_from_coaches)

    def test_therapist_saves_therapist_fields(self):
        self._login_tp()
        resp = self._save(self.player, 'allergies', ' Pollen ')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['value'], 'Pollen')
        resp = self._save(self.injury, 'internal_notes', 'TP-only synthetic text')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.sudo().internal_notes, 'TP-only synthetic text')
        resp = self._save(self.injury, 'hidden_from_coaches', '1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertTrue(self.injury.hidden_from_coaches)

    def test_unknown_field_forbidden(self):
        self._login_tp()
        resp = self._save(self.player, 'name', 'Hijack')
        self.assertEqual(resp.status_code, 403)
        resp = self._save(self.injury, 'patient_id', str(self.player_b.id))
        self.assertEqual(resp.status_code, 403)

    def test_other_team_forbidden(self):
        self._login_tp()
        resp = self._save(self.player_b, 'position', 'Goalie')
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(self.player_b.position)

    # -- UC-R2 -----------------------------------------------------------
    def test_blur_save_one_history_row(self):
        self._login_coach()
        before = self._history_count(self.injury)
        resp = self._save(self.injury, 'external_notes', 'Rest two days (synthetic)')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(self._history_count(self.injury), before + 1)
        row = self.env['sports.injury.note.history'].search(
            [('injury_id', '=', self.injury.id)], order='id desc', limit=1)
        self.assertEqual(row.scope, 'external')
        self.assertEqual(row.author_id, self.coach)
        # Same value again: no second row.
        resp = self._save(self.injury, 'external_notes', 'Rest two days (synthetic)')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._history_count(self.injury), before + 1)

    def test_stale_write_date_conflict(self):
        self._login_tp()
        resp = self._save(self.injury, 'external_notes', 'Mine', write_date='2000-01-01 00:00:00')
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertTrue(body['conflict'])
        self.injury.invalidate_recordset()
        self.assertFalse(self.injury.external_notes)

    # -- UC-R3 -----------------------------------------------------------
    def test_status_pair_saved_atomically(self):
        self._login_tp()
        resp = self._save(self.player, 'sc_status', 'no:no_contact')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['value'], 'no:no_contact')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status),
                         ('no', 'no_contact'))
        resp = self._save(self.player, 'sc_status', 'yes:no')
        self.assertEqual(resp.status_code, 400)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status),
                         ('no', 'no_contact'))

    # -- UC-R4 -----------------------------------------------------------
    def test_coach_rename_and_blank_refused(self):
        self._login_coach()
        resp = self._save(self.player, 'first_name', 'Patrick')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Patrick')
        self.assertIn('Patrick', self.player.partner_id.name)
        resp = self._save(self.player, 'last_name', '   ')
        self.assertEqual(resp.status_code, 400)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.last_name, 'One')

    def test_jersey_normalised_and_duplicate_message(self):
        self._login_coach()
        resp = self._save(self.player, 'jersey_number', '#12')
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body['value'], '12')
        self.assertIn('Mate', body.get('message', ''))
        resp = self._save(self.player, 'jersey_number', ' 7 ')
        self.assertEqual(resp.json()['value'], '7')
        self.assertFalse(resp.json().get('message'))

    # -- UC-R5 -----------------------------------------------------------
    def test_coach_diagnosis_only_while_unverified(self):
        self._login_coach()
        resp = self._save(self.injury, 'diagnosis', 'Coach wording')
        self.assertEqual(resp.status_code, 403)
        fresh = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Reported'})
        # Created by an internal user: force the coach-report stage.
        fresh.with_context(mail_notrack=True).write({'stage': 'unverified'})
        resp = self._save(fresh, 'diagnosis', 'Reworded by coach')
        self.assertEqual(resp.status_code, 200, resp.text)
        fresh.invalidate_recordset()
        self.assertEqual(fresh.diagnosis, 'Reworded by coach')

    def test_resolve_sets_resolution_date(self):
        self._login_tp()
        resp = self._save(self.injury, 'stage', 'resolved')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertTrue(self.injury.resolution_date)
        resp = self._save(self.injury, 'stage', 'nonsense')
        self.assertEqual(resp.status_code, 400)

    def test_injury_date_and_na_are_one_value(self):
        self._login_coach()
        resp = self._save(self.injury, 'sc_injury_date', 'na')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertTrue(self.injury.injury_date_na)
        self.assertFalse(self.injury.injury_date)
        resp = self._save(self.injury, 'sc_injury_date', '2026-03-04')
        self.assertEqual(resp.json()['value'], '2026-03-04')
        self.injury.invalidate_recordset()
        self.assertFalse(self.injury.injury_date_na)
        resp = self._save(self.injury, 'sc_injury_date', '')
        self.assertEqual(resp.status_code, 400)

    # -- UC-R6 -----------------------------------------------------------
    def test_note_edit_author_only(self):
        self._login_tp()
        resp = self._save(self.note, 'note', 'Edited by the author')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.note.invalidate_recordset()
        self.assertEqual(self.note.note, 'Edited by the author')
        self.authenticate('t1539.tp2@example.com', 't1539-tp2-pass')
        resp = self._save(self.note, 'note', 'Hijacked by another TP')
        self.assertEqual(resp.status_code, 403)
        self._login_coach()
        resp = self._save(self.note, 'note', 'Hijacked by a coach')
        self.assertEqual(resp.status_code, 403)
        self.note.invalidate_recordset()
        self.assertEqual(self.note.note, 'Edited by the author')
        self._login_tp()
        resp = self._save(self.note, 'note', '  ')
        self.assertEqual(resp.status_code, 400)

    # -- UC-R7 -----------------------------------------------------------
    def test_coach_edits_primary_contact(self):
        self._login_coach()
        resp = self._save(self.contact, 'mobile', '555-0100')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.contact.invalidate_recordset()
        self.assertEqual(self.contact.mobile, '555-0100')
        resp = self._save(self.contact, 'name', '')
        self.assertEqual(resp.status_code, 400)

    # -- UC-R8 -----------------------------------------------------------
    def test_sudo_spec_requires_permission(self):
        app_shell._validate_save_registry(app_shell.SAVE_REGISTRY)
        with self.assertRaises(AssertionError):
            app_shell._validate_save_registry({'x.model': {
                'fields': ('a',), 'check': lambda c, r: None,
                'write': lambda c, r, f, v: None, 'sudo_write': True}})

    @mute_logger('odoo.http')
    def test_csrf_required(self):
        self._login_tp()
        resp = self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data={
            'field': 'position', 'value': 'Wing', 'write_date': self._wd(self.player)})
        self.assertEqual(resp.status_code, 400)
