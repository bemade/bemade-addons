"""Task 1411 — clinic dossier: injury notes (external + TP-only internal) and
the training recommendation editable in place, the patient's TP notes shown
read-only, light-red active-injury cards, and a quick edit of the match /
practice statuses.

Covered here (HttpCase round-trips, synthetic fixtures — this addon's
repository is public):

* the dossier renders one card per active injury (#clinic-injury-<id>,
  bg-danger-subtle header) with both note textareas and the quick status /
  recommendation forms for a treatment professional. (The non-TP rendering of
  that page — no internal notes, no forms — is defence in depth only: the
  clinic page admits TPs and system admins, and an admin without a TP group
  cannot read injuries at all today, so no real role reaches it.);
* /my/injury/save with partial=1 writes ONLY the note fields present (no
  clobbering of diagnosis / stage / TPs / absent notes), honours the #1404
  blank-row rule, ignores internal_notes from a non-TP, and returns to the
  clinic with the card anchor; without partial=1 the route behaves as before;
* /my/player/<id>/quick: TP-only (403 otherwise), whitelisted fields, the
  match/practice combination validated server-side — an invalid pair writes
  nothing and bounces back with error=invalid_status_combo (the refused pair
  re-shown inline); a valid save keeps ?patient= and is tracked in chatter.

NOT claimed: the browser click-through (the anchor scroll, the select snap
script, phone layout). That is the /dev-review UAT.
"""
import re
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestClinicDossier1411(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        cls.org = env['res.partner'].create({'name': 'CD Org', 'is_company': True})
        cls.team = env['sports.team'].create({'name': 'CD Team', 'parent_id': cls.org.id})

        portal_g = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id

        def _user(name, login, password, groups):
            return env['res.users'].with_context(no_reset_password=True).create({
                'name': name, 'login': login, 'password': password,
                'group_ids': [Command.set(groups)],
            })

        cls.tp = _user('CD Therapist', 'cd.tp@example.com', 'cd-tp', [portal_g, tp_g])
        cls.coach = _user('CD Coach', 'cd.coach@example.com', 'cd-coach', [portal_g, coach_g])
        # Staff on the team but in NO treatment-professional group: proves the
        # quick route gates on the TP groups, not on team access.
        cls.staffer = _user('CD Staffer', 'cd.staffer@example.com', 'cd-staffer', [portal_g])
        for user, role in ((cls.tp, 'therapist'), (cls.coach, 'coach'), (cls.staffer, 'coach')):
            env['sports.team.staff'].create({
                'team_id': cls.team.id, 'partner_id': user.partner_id.id, 'role': role,
            })

        cls.patient = env['sports.patient'].create({
            'first_name': 'Dora', 'last_name': 'Dossier',
            'match_status': 'yes', 'practice_status': 'yes',
            'training_recommendation': 'Synthetic rec v1',
            'team_info_notes': 'Synthetic player notes',
        })
        cls.patient.team_ids = [Command.set([cls.team.id])]

        cls.injury = env['sports.patient.injury'].create({
            'patient_id': cls.patient.id, 'team_id': cls.team.id,
            'diagnosis': 'Synthetic strain',
            'external_notes': 'ext v1', 'internal_notes': 'int v1',
            'predicted_resolution_date': fields.Date.today() + timedelta(days=10),
        })
        cls.injury.with_context(mail_notrack=True).write({
            'stage': 'active',
            'treatment_professional_ids': [Command.set([cls.tp.id])],
        })

        now = fields.Datetime.now()
        cls.clinic = env['sports.event'].create({
            'name': 'CD Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([cls.team.id])],
            'date_start': now + timedelta(minutes=30),
            'date_end': now + timedelta(hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        env['sports.clinic.attendance'].create({
            'event_id': cls.clinic.id, 'patient_id': cls.patient.id})

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
    def injury_return_url(self):
        return '/my/clinic/%s?patient=%s#clinic-injury-%s' % (
            self.clinic.id, self.patient.id, self.injury.id)

    @property
    def quick_url(self):
        return '/my/player/%s/quick' % self.patient.id

    def _refresh(self):
        self.patient.invalidate_recordset()
        self.injury.invalidate_recordset()

    def _history_count(self):
        return self.env['sports.injury.note.history'].sudo().search_count(
            [('injury_id', '=', self.injury.id)])

    def _post_quick(self, data, **extra):
        payload = {'csrf_token': self._csrf(), 'return_url': self.dossier_url + '#clinic-dossier'}
        payload.update(data)
        payload.update(extra)
        return self.url_open(self.quick_url, data=payload, allow_redirects=False)

    # ==================================================================
    # dossier rendering
    # ==================================================================
    def test_dossier_renders_injury_cards_for_tp(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        html = self.url_open(self.dossier_url).text
        self.assertIn('id="clinic-injury-%s"' % self.injury.id, html)
        self.assertIn('bg-danger-subtle', html)
        self.assertIn('Synthetic strain', html)
        # Both note fields, pre-filled, in a partial form returning to this card.
        self.assertRegex(html, r'<textarea name="external_notes"[^>]*>\s*ext v1\s*</textarea>')
        self.assertRegex(html, r'<textarea name="internal_notes"[^>]*>\s*int v1\s*</textarea>')
        self.assertIn('name="partial" value="1"', html)
        self.assertIn('value="%s"' % self.injury_return_url, html)
        self.assertIn('action="/my/injury/save"', html)
        # Patient block: quick status form + recommendation + read-only notes.
        self.assertIn('action="%s"' % self.quick_url, html)
        self.assertIn('name="match_status"', html)
        self.assertIn('name="practice_status"', html)
        self.assertRegex(html, r'<textarea name="training_recommendation"[^>]*>\s*Synthetic rec v1\s*</textarea>')
        self.assertIn('Synthetic player notes', html)
        self.assertIn('id="clinic-player-notes"', html)
        # Return URL of the quick forms: same clinic, same patient, dossier anchor.
        self.assertIn('value="%s#clinic-dossier"' % self.dossier_url, html)
        # No inline status error without one.
        self.assertNotIn('Invalid status combination', html)

    def test_dossier_shows_inline_error_and_refused_pair(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        html = self.url_open(
            self.dossier_url + '&error=invalid_status_combo&match_status=yes&practice_status=no'
            '#clinic-dossier').text
        self.assertIn('Invalid status combination', html)
        # The refused pair is re-selected so the therapist sees what bounced.
        self.assertRegex(html, r'<option value="yes"\s+selected="selected">')
        practice = re.search(r'<select name="practice_status".*?</select>', html, re.S).group(0)
        self.assertRegex(practice, r'<option value="no"\s+selected="selected">')
        # Not duplicated as a top-of-page alert.
        self.assertNotIn('alert alert-danger', html)

    # ==================================================================
    # /my/injury/save — partial payload
    # ==================================================================
    def test_partial_save_writes_only_present_fields(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        before = self._history_count()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'ext v2', 'return_url': self.injury_return_url,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/clinic/%s?patient=%s&success=injury_updated#clinic-injury-%s' % (
                self.clinic.id, self.patient.id, self.injury.id))
        self._refresh()
        self.assertEqual(self.injury.external_notes, 'ext v2')
        # Absent fields untouched: internal notes, diagnosis, stage, TPs.
        self.assertEqual(self.injury.internal_notes, 'int v1')
        self.assertEqual(self.injury.diagnosis, 'Synthetic strain')
        self.assertEqual(self.injury.stage, 'active')
        self.assertEqual(self.injury.treatment_professional_ids, self.tp)
        self.assertEqual(self._history_count(), before + 1)

    def test_partial_save_internal_notes_tp_and_blank_rule(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        token = self._csrf()
        before = self._history_count()
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token, 'injury_id': self.injury.id, 'partial': '1',
            'internal_notes': 'int v2', 'return_url': self.injury_return_url,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self._refresh()
        self.assertEqual(self.injury.internal_notes, 'int v2')
        self.assertEqual(self.injury.external_notes, 'ext v1')
        self.assertEqual(self._history_count(), before + 1)
        # Whitespace-only ⇒ a genuine clear, and NO history row (#1404).
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token, 'injury_id': self.injury.id, 'partial': '1',
            'internal_notes': '   ', 'return_url': self.injury_return_url,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self._refresh()
        self.assertFalse(self.injury.internal_notes)
        self.assertEqual(self._history_count(), before + 1)
        # Unchanged value ⇒ no row either.
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': token, 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'ext v1', 'return_url': self.injury_return_url,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(self._history_count(), before + 1)

    def test_partial_save_non_tp_internal_notes_ignored(self):
        self.authenticate('cd.coach@example.com', 'cd-coach')
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'ext by coach', 'internal_notes': 'sneaky',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        # No return_url ⇒ the edit form, as the full save does.
        self.assertIn('/my/injury/edit?injury_id=%s' % self.injury.id, resp.headers['Location'])
        self._refresh()
        self.assertEqual(self.injury.external_notes, 'ext by coach')
        self.assertEqual(self.injury.internal_notes, 'int v1')

    def test_partial_save_offhost_return_url_falls_back(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id, 'partial': '1',
            'external_notes': 'ext v3', 'return_url': 'https://evil.example.com/x',
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].startswith('/my/injury/edit?injury_id=%s' % self.injury.id))

    def test_full_save_unchanged_without_partial(self):
        """The edit form's behaviour today: diagnosis/external written, absent
        internal notes left alone, the redirect goes to the edit form."""
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self.url_open('/my/injury/save', data={
            'csrf_token': self._csrf(), 'injury_id': self.injury.id,
            'diagnosis': 'Synthetic strain (full)', 'external_notes': 'ext full',
            'treatment_professional_ids[]': self.tp.id,
            'return_url': self.injury_return_url,
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].startswith(
            '/my/injury/edit?injury_id=%s&success=injury_updated' % self.injury.id))
        self._refresh()
        self.assertEqual(self.injury.diagnosis, 'Synthetic strain (full)')
        self.assertEqual(self.injury.external_notes, 'ext full')
        self.assertEqual(self.injury.internal_notes, 'int v1')

    # ==================================================================
    # /my/player/<id>/quick
    # ==================================================================
    def test_quick_coach_forbidden(self):
        self.authenticate('cd.coach@example.com', 'cd-coach')
        resp = self._post_quick({'match_status': 'no', 'practice_status': 'no'})
        self.assertEqual(resp.status_code, 403)
        self._refresh()
        self.assertEqual(self.patient.match_status, 'yes')

    def test_quick_staffer_without_tp_group_forbidden(self):
        self.authenticate('cd.staffer@example.com', 'cd-staffer')
        resp = self._post_quick({'training_recommendation': 'nope'})
        self.assertEqual(resp.status_code, 403)
        self._refresh()
        self.assertEqual(self.patient.training_recommendation, 'Synthetic rec v1')

    def test_quick_tp_saves_statuses_and_tracks(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self._post_quick({'match_status': 'no', 'practice_status': 'no_contact'})
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            self.dossier_url + '&success=player_updated#clinic-dossier')
        self._refresh()
        self.assertEqual(self.patient.match_status, 'no')
        self.assertEqual(self.patient.practice_status, 'no_contact')
        self.assertEqual(self.patient.training_recommendation, 'Synthetic rec v1')
        # Chatter tracking (tracking=True on both fields) logged the change.
        self.env.flush_all()
        tracked = self.env['mail.tracking.value'].sudo().search([
            ('mail_message_id.model', '=', 'sports.patient'),
            ('mail_message_id.res_id', '=', self.patient.id),
            ('field_id.name', 'in', ('match_status', 'practice_status')),
        ])
        self.assertEqual(set(tracked.mapped('field_id.name')), {'match_status', 'practice_status'})
        # The dossier now shows the new badges.
        html = self.url_open(self.dossier_url).text
        self.assertIn('title="Match: No"', html)
        self.assertIn('title="Practice: Yes - No Contact"', html)

    def test_quick_tp_saves_recommendation_only(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self._post_quick({'training_recommendation': '  Synthetic rec v2  '})
        self.assertEqual(resp.status_code, 303)
        self._refresh()
        self.assertEqual(self.patient.training_recommendation, 'Synthetic rec v2')
        self.assertEqual((self.patient.match_status, self.patient.practice_status), ('yes', 'yes'))
        # Blank ⇒ cleared.
        resp = self._post_quick({'training_recommendation': '   '})
        self.assertEqual(resp.status_code, 303)
        self._refresh()
        self.assertFalse(self.patient.training_recommendation)

    def test_quick_invalid_combination_writes_nothing(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self._post_quick({'match_status': 'yes', 'practice_status': 'no',
                                 'training_recommendation': 'should not land'})
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            self.dossier_url + '&error=invalid_status_combo&match_status=yes&practice_status=no'
            '#clinic-dossier')
        self._refresh()
        self.assertEqual((self.patient.match_status, self.patient.practice_status), ('yes', 'yes'))
        self.assertEqual(self.patient.training_recommendation, 'Synthetic rec v1')
        # A single posted status is combined with the stored other one.
        resp = self._post_quick({'practice_status': 'no'})   # stored match = yes ⇒ invalid
        self.assertEqual(resp.status_code, 303)
        self.assertIn('error=invalid_status_combo', resp.headers['Location'])
        self._refresh()
        self.assertEqual(self.patient.practice_status, 'yes')

    def test_quick_unknown_value_is_refused(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self._post_quick({'match_status': 'maybe', 'practice_status': 'yes'})
        self.assertEqual(resp.status_code, 303)
        self.assertIn('error=invalid_status_combo', resp.headers['Location'])
        self._refresh()
        self.assertEqual(self.patient.match_status, 'yes')

    def test_quick_ignores_non_whitelisted_fields(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self._post_quick({'training_recommendation': 'rec v3',
                                 'first_name': 'Hacked', 'allergies': 'peanuts'})
        self.assertEqual(resp.status_code, 303)
        self._refresh()
        self.assertEqual(self.patient.first_name, 'Dora')
        self.assertFalse(self.patient.sudo().allergies)

    def test_quick_offhost_return_url_falls_back(self):
        self.authenticate('cd.tp@example.com', 'cd-tp')
        resp = self._post_quick({'training_recommendation': 'rec v4'},
                                return_url='//evil.example.com/x')
        self.assertEqual(resp.status_code, 303)
        self.assertEqual(
            resp.headers['Location'],
            '/my/player?player_id=%s&success=player_updated' % self.patient.id)
