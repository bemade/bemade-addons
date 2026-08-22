"""Task 1413 — treatment notes: editable after addition (author / clinic
admin, tracked in chatter) + the « Linked injury » select in the clinic
add-note form.

Covered here (HttpCase round-trips, synthetic fixtures — this addon's
repository is public):

* the clinic add-note form offers « General note » + the patient's ACTIVE
  injuries, the single active injury preselected (General when there are two);
  adding with injury_id links the note (and still stamps the clinic); an
  injury of another patient is refused, nothing written;
* the dossier table and the player notes tab show « Edit » ONLY on the notes
  the viewer may edit (author / clinic admin);
* POST /my/injury/note/<id>/edit: author OK from the clinic and from the
  player page (text / date / injury changed, tracking values on the note's
  chatter, « modified on … by … » rendered), clinic admin OK, another TP →
  error=not_author (nothing written, inline message on the re-opened form),
  coach → 403, empty text → error=empty_note, foreign injury →
  error=invalid_injury;
* the model's write() guard refuses a portal user rewriting someone else's
  note even under sudo; a fresh note is never « modified ».

NOT claimed: the browser click-through (the <details> toggle, « Cancel »,
the select default as seen, phone layout). That is the /dev-review UAT.
"""
import re
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import mute_logger


@tagged('-at_install', 'post_install')
class TestClinicNotesEdit1413(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'NE Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'NE Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        internal_g = env.ref('base.group_user').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        int_tp_g = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id
        admin_g = env.ref('bemade_sports_clinic.group_sports_clinic_admin').id

        def _user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _user('Nina Therapist', 'ne.tp@example.com', 'ne-tp-pass', [portal_g, tp_g])
        cls.tp2 = _user('Omar Other', 'ne.tp2@example.com', 'ne-tp2-pass', [portal_g, tp_g])
        cls.coach = _user('Carl Coach', 'ne.coach@example.com', 'ne-coach-pass', [portal_g, coach_g])
        # Internal clinic admin (NOT base.group_system): team-gated like
        # everyone, allowed to edit any note by the admin rule.
        cls.admin = _user('Ada Admin', 'ne.admin@example.com', 'ne-admin-pass',
                          [internal_g, int_tp_g, admin_g])
        for user, role in ((cls.tp, 'therapist'), (cls.tp2, 'therapist'),
                           (cls.coach, 'coach'), (cls.admin, 'therapist')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        cls.patient = env['sports.patient'].create({
            'first_name': 'Nina', 'last_name': 'Notes'})
        cls.patient.team_ids = [Command.set([cls.team.id])]
        cls.other_patient = env['sports.patient'].create({
            'first_name': 'Otto', 'last_name': 'Other'})
        cls.other_patient.team_ids = [Command.set([cls.team.id])]

        def _injury(patient, diagnosis):
            inj = env['sports.patient.injury'].create({
                'patient_id': patient.id,
                'diagnosis': diagnosis,
                'predicted_resolution_date': fields.Date.today() + timedelta(days=10),
            })
            inj.with_context(mail_notrack=True).write({'stage': 'active'})
            return inj

        cls.injury = _injury(cls.patient, 'Synthetic sprain A')
        cls.foreign_injury = _injury(cls.other_patient, 'Synthetic foreign strain')

        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'NE Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': now + timedelta(minutes=30),
            'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id, cls.tp2.id])],
        })
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.patient.id})

        Note = env['sports.treatment.note']
        cls.note_tp = Note.create({
            'patient_id': cls.patient.id, 'note': 'Synthetic note by TP one',
            'date': fields.Date.today() - timedelta(days=3), 'user_id': cls.tp.id,
        })
        cls.note_tp2 = Note.create({
            'patient_id': cls.patient.id, 'note': 'Synthetic note by TP two',
            'date': fields.Date.today() - timedelta(days=2), 'user_id': cls.tp2.id,
        })
        # Notes « added yesterday »: cr.now() is cached per transaction, so
        # without this a same-transaction edit would share the creation
        # timestamp and never read as modified. Flush first: a pending
        # computed-field write after the UPDATE would re-stamp write_date.
        env.flush_all()
        env.cr.execute(
            "UPDATE sports_treatment_note SET create_date = create_date - interval '1 day', "
            "write_date = write_date - interval '1 day' WHERE id IN %s",
            [tuple((cls.note_tp + cls.note_tp2).ids)])
        (cls.note_tp + cls.note_tp2).invalidate_recordset()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _csrf(self):
        resp = self.url_open('/my')
        match = re.search(r'csrf_token:\s*"([^"]+)"', resp.text)
        return match.group(1) if match else ''

    @property
    def dossier_url(self):
        return '/my/clinic/%s?patient=%s' % (self.clinic.id, self.patient.id)

    @property
    def clinic_notes_return(self):
        return self.dossier_url + '#clinic-notes'

    @property
    def player_notes_return(self):
        return '/my/player?player_id=%s&clinic_id=%s#notes' % (self.patient.id, self.clinic.id)

    def _edit_url(self, note):
        return '/my/injury/note/%s/edit' % note.id

    def _post_edit(self, note, data, return_url=None):
        payload = {'csrf_token': self._csrf(),
                   'return_url': return_url or self.clinic_notes_return}
        payload.update(data)
        return self.url_open(self._edit_url(note), data=payload, allow_redirects=False)

    def _note_count(self):
        return self.env['sports.treatment.note'].sudo().search_count(
            [('patient_id', '=', self.patient.id)])

    def _select_block(self, html, select_id):
        match = re.search(r'<select name="injury_id" id="%s".*?</select>' % select_id, html, re.S)
        self.assertTrue(match, 'select %s not rendered' % select_id)
        return match.group(0)

    # ==================================================================
    # clinic add-note form: « Linked injury » select
    # ==================================================================
    def test_clinic_select_default_single_active_injury(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        html = self.url_open(self.dossier_url).text
        block = self._select_block(html, 'clinic_note_injury')
        self.assertIn('<option value="">', block)
        self.assertRegex(block, r'<option value="%s"\s+selected="selected">' % self.injury.id)
        self.assertIn('Synthetic sprain A', block)

    def test_clinic_select_default_general_with_two_active(self):
        second = self.env['sports.patient.injury'].create({
            'patient_id': self.patient.id,
            'diagnosis': 'Synthetic sprain B',
        })
        second.with_context(mail_notrack=True).write({'stage': 'active'})
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        html = self.url_open(self.dossier_url).text
        block = self._select_block(html, 'clinic_note_injury')
        self.assertIn('Synthetic sprain A', block)
        self.assertIn('Synthetic sprain B', block)
        self.assertNotIn('selected="selected"', block)

    def test_clinic_add_note_with_injury_links_it(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        before = self._note_count()
        resp = self.url_open('/my/injury/note/add', data={
            'csrf_token': self._csrf(), 'patient_id': self.patient.id,
            'event_id': self.clinic.id, 'injury_id': self.injury.id,
            'note': 'Synthetic linked note', 'return_url': self.clinic_notes_return,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], self.dossier_url + '&success=note_added#clinic-notes')
        self.assertEqual(self._note_count(), before + 1)
        note = self.env['sports.treatment.note'].sudo().search(
            [('patient_id', '=', self.patient.id)], order='id desc', limit=1)
        self.assertEqual(note.injury_id, self.injury)
        self.assertEqual(note.event_id, self.clinic)
        self.assertEqual(note.user_id, self.tp)
        self.assertEqual(note.note_type, 'injury')
        # A fresh note is never « modified ».
        self.assertFalse(note.modified_label)
        # The dossier shows the injury badge on the new row.
        html = self.url_open(self.dossier_url).text
        self.assertIn('o_sc_note_injury', html)

    def test_clinic_add_note_foreign_injury_refused(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        before = self._note_count()
        resp = self.url_open('/my/injury/note/add', data={
            'csrf_token': self._csrf(), 'patient_id': self.patient.id,
            'event_id': self.clinic.id, 'injury_id': self.foreign_injury.id,
            'note': 'Synthetic misfiled note', 'return_url': self.clinic_notes_return,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], self.dossier_url + '&error=invalid_injury#clinic-notes')
        self.assertEqual(self._note_count(), before)
        self.assertEqual(self.env['sports.treatment.note'].sudo().search_count(
            [('patient_id', '=', self.other_patient.id)]), 0)
        html = self.url_open(resp.headers['Location']).text
        self.assertIn('The selected injury does not belong to this patient.', html)

    # ==================================================================
    # « Edit » control visibility
    # ==================================================================
    def test_dossier_edit_control_only_on_own_notes(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        html = self.url_open(self.dossier_url).text
        self.assertIn('action="%s"' % self._edit_url(self.note_tp), html)
        self.assertNotIn('action="%s"' % self._edit_url(self.note_tp2), html)
        self.assertNotIn('o_sc_note_modified', html)
        # The edit form is prefilled with the stored values and returns here.
        self.assertRegex(html, r'<textarea name="note"[^>]*>\s*Synthetic note by TP one\s*</textarea>')
        self.assertIn('value="%s"' % self.clinic_notes_return, html)

    def test_player_page_edit_control_only_on_own_notes(self):
        self.authenticate('ne.tp2@example.com', 'ne-tp2-pass')
        html = self.url_open('/my/player?player_id=%s&clinic_id=%s' % (
            self.patient.id, self.clinic.id)).text
        self.assertIn('action="%s"' % self._edit_url(self.note_tp2), html)
        self.assertNotIn('action="%s"' % self._edit_url(self.note_tp), html)
        self.assertIn('value="%s"' % self.player_notes_return.replace('&', '&amp;'), html)

    def test_admin_sees_edit_on_every_note(self):
        self.authenticate('ne.admin@example.com', 'ne-admin-pass')
        html = self.url_open(self.dossier_url).text
        self.assertIn('action="%s"' % self._edit_url(self.note_tp), html)
        self.assertIn('action="%s"' % self._edit_url(self.note_tp2), html)

    # ==================================================================
    # POST /my/injury/note/<id>/edit
    # ==================================================================
    def test_author_edit_ok_from_clinic(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        new_date = fields.Date.today() - timedelta(days=1)
        resp = self._post_edit(self.note_tp, {
            'note': '  Synthetic note by TP one — revised  ',
            'date': new_date.isoformat(), 'injury_id': self.injury.id,
        })
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(resp.headers['Location'], self.dossier_url + '&success=note_updated#clinic-notes')
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one — revised')
        self.assertEqual(self.note_tp.date, new_date)
        self.assertEqual(self.note_tp.injury_id, self.injury)
        self.assertEqual(self.note_tp.user_id, self.tp)
        # The change is logged on the note's chatter (tracked fields).
        tracked = self.note_tp.message_ids.tracking_value_ids.mapped('field_id.name')
        self.assertIn('note', tracked)
        self.assertIn('injury_id', tracked)
        # « modified on … by <initials> » — by the editor (NT), visible on both pages.
        self.assertTrue(self.note_tp.modified_label)
        self.assertIn('NT', self.note_tp.modified_label)
        html = self.url_open(resp.headers['Location']).text
        self.assertIn('Treatment note updated.', html)
        self.assertIn('o_sc_note_modified', html)
        self.assertIn('o_sc_note_injury', html)
        html = self.url_open('/my/player?player_id=%s' % self.patient.id).text
        self.assertIn('o_sc_note_modified', html)
        # The other note is untouched and still not « modified ».
        self.note_tp2.invalidate_recordset()
        self.assertFalse(self.note_tp2.modified_label)

    def test_author_edit_ok_from_player_page(self):
        self.authenticate('ne.tp2@example.com', 'ne-tp2-pass')
        resp = self._post_edit(self.note_tp2, {
            'note': 'Synthetic note by TP two — revised', 'date': self.note_tp2.date.isoformat(),
            'injury_id': '',
        }, return_url=self.player_notes_return)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/player?player_id=%s&clinic_id=%s&success=note_updated#notes' % (
                self.patient.id, self.clinic.id))
        self.note_tp2.invalidate_recordset()
        self.assertEqual(self.note_tp2.note, 'Synthetic note by TP two — revised')
        self.assertFalse(self.note_tp2.injury_id)
        html = self.url_open(resp.headers['Location']).text
        self.assertIn('Treatment note updated.', html)
        self.assertIn('o_sc_note_modified', html)

    def test_admin_edit_ok(self):
        self.authenticate('ne.admin@example.com', 'ne-admin-pass')
        resp = self._post_edit(self.note_tp, {
            'note': 'Synthetic note by TP one — admin revised', 'date': self.note_tp.date.isoformat(),
            'injury_id': '',
        })
        self.assertEqual(resp.status_code, 303)
        self.assertIn('success=note_updated', resp.headers['Location'])
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one — admin revised')
        self.assertEqual(self.note_tp.user_id, self.tp)  # author never changes
        self.assertIn('AA', self.note_tp.modified_label)

    def test_other_tp_refused_not_author(self):
        self.authenticate('ne.tp2@example.com', 'ne-tp2-pass')
        resp = self._post_edit(self.note_tp, {
            'note': 'Synthetic hijack', 'date': self.note_tp.date.isoformat(), 'injury_id': '',
        })
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            self.dossier_url + '&error=not_author&note_id=%s#clinic-notes' % self.note_tp.id)
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one')
        self.assertFalse(self.note_tp.modified_label)
        # The bounce page carries no inline form for that note (not editable by
        # tp2) and no top alert either — the error is keyed to the note.
        html = self.url_open(resp.headers['Location']).text
        self.assertNotIn('alert alert-danger', html)
        self.assertNotIn('action="%s"' % self._edit_url(self.note_tp), html)

    def test_coach_forbidden(self):
        self.authenticate('ne.coach@example.com', 'ne-coach-pass')
        resp = self._post_edit(self.note_tp, {
            'note': 'Synthetic coach edit', 'date': self.note_tp.date.isoformat(), 'injury_id': '',
        })
        self.assertEqual(resp.status_code, 403)
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one')

    def test_unknown_note_404(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        resp = self.url_open('/my/injury/note/999999999/edit', data={
            'csrf_token': self._csrf(), 'note': 'x'}, allow_redirects=False)
        self.assertEqual(resp.status_code, 404)

    def test_empty_note_refused_inline(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        resp = self._post_edit(self.note_tp, {
            'note': '   \n  ', 'date': self.note_tp.date.isoformat(), 'injury_id': self.injury.id,
        })
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            self.dossier_url + '&error=empty_note&note_id=%s#clinic-notes' % self.note_tp.id)
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one')
        self.assertFalse(self.note_tp.injury_id)
        html = self.url_open(resp.headers['Location']).text
        # That note's form is re-opened with the error inline, no top alert.
        self.assertRegex(html, r'<details class="o_sc_note_edit[^"]*"\s+open="open">')
        self.assertIn('Please enter a treatment note.', html)
        self.assertNotIn('alert alert-danger', html)

    def test_foreign_injury_refused_on_edit(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        resp = self._post_edit(self.note_tp, {
            'note': 'Synthetic relink', 'date': self.note_tp.date.isoformat(),
            'injury_id': self.foreign_injury.id,
        })
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            self.dossier_url + '&error=invalid_injury&note_id=%s#clinic-notes' % self.note_tp.id)
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one')
        self.assertFalse(self.note_tp.injury_id)
        html = self.url_open(resp.headers['Location']).text
        self.assertIn('The selected injury does not belong to this patient.', html)

    def test_invalid_date_refused(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        resp = self._post_edit(self.note_tp, {
            'note': 'Synthetic redate', 'date': 'not-a-date', 'injury_id': '',
        })
        self.assertEqual(resp.status_code, 303)
        self.assertIn('error=invalid_date&note_id=%s' % self.note_tp.id, resp.headers['Location'])
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one')

    def test_return_url_must_be_local(self):
        self.authenticate('ne.tp@example.com', 'ne-tp-pass')
        resp = self._post_edit(self.note_tp, {
            'note': 'Synthetic offsite', 'date': self.note_tp.date.isoformat(), 'injury_id': '',
        }, return_url='https://example.com/evil')
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/patient/notes?patient_id=%s&success=note_updated' % self.patient.id)

    # ==================================================================
    # model guard
    # ==================================================================
    def test_write_guard_refuses_portal_non_author_even_sudo(self):
        with mute_logger('odoo.addons.base.models.ir_model'), self.assertRaises(AccessError):
            self.note_tp.with_user(self.tp2).sudo().write({'note': 'Synthetic hijack'})
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one')
        # The author may; so may the clinic admin.
        self.note_tp.with_user(self.tp).sudo().write({'note': 'Synthetic note by TP one v2'})
        self.note_tp.with_user(self.admin).sudo().write({'note': 'Synthetic note by TP one v3'})
        self.note_tp.invalidate_recordset()
        self.assertEqual(self.note_tp.note, 'Synthetic note by TP one v3')

    def test_can_portal_edit_predicate(self):
        self.assertTrue(self.note_tp._can_portal_edit(self.tp))
        self.assertFalse(self.note_tp._can_portal_edit(self.tp2))
        self.assertFalse(self.note_tp._can_portal_edit(self.coach))
        self.assertTrue(self.note_tp._can_portal_edit(self.admin))
        self.assertTrue(self.note_tp2._can_portal_edit(self.tp2))
