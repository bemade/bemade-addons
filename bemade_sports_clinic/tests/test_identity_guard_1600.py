"""Task 1600 — a portal save must never write another player's identity.
Synthetic fixtures only (public repository).

Acceptance criteria covered:

* AC-b  A save refused after the patient write leaves the patient unchanged
  (/my/player/save runs in a savepoint).
* AC-c  A portal save or create giving a player the first name + last name
  + date of birth (case-insensitive, trimmed) of ANOTHER player — active or
  archived — is refused (« Another player already has this name and date of
  birth. »); the same values on the same player are fine; internal users are
  not refused (the backend merge flows stay possible).
* AC-d  A portal user changing an EXISTING first name, last name or date of
  birth without the confirmation is refused; with it the change is saved and
  an audit note (who, field, old → new) is posted on the player's file.
  Filling a blank field needs no confirmation. Internal users are unaffected.
  The legacy form passes the confirmation only when ``identity_confirmed=1``
  is posted, and only writes the identity fields that changed.
* AC-e  The app-shell pencil (POST /my/app/save) answers 428
  ``confirm_identity`` (old → new, nothing written) without ``confirm=1``,
  and saves + records with it.
* AC-f  Unticking a team on the legacy edit form is the official removal:
  the pending-removal flag is cleared, the removal note is posted, the open
  « Player Removal Request » activity is closed; the player's teams that are
  not the user's are untouched. A save that drops the user's last team lands
  on the players list (no 403) and leaves no flash behind.
* AC-g  The 19.0.1.60.0 post-migrate clears the flag and closes the removal
  activities only of pending-removal players with no team (active or
  archived); players who still have a team are untouched.
"""
import importlib.util
import os
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .portal_cov_common import PortalCovCommon

SWITCH = 'bemade_sports_clinic.app_shell_enabled'


def _load_migration():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'migrations', '19.0.1.60.0', 'post-migrate.py')
    spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_60_0', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IdentityCommon(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.team_c = env['sports.team'].create({'name': 'PC Team C 1600', 'parent_id': cls.org.id})
        env['sports.team.staff'].create({
            'team_id': cls.team_c.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })
        cls.player.write({'date_of_birth': '2008-03-04'})
        # Another file with a known identity (the duplicate target).
        cls.other = env['sports.patient'].create({
            'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': '2010-01-02',
            'team_ids': [Command.set([cls.team_b.id])],
        })
        cls.internal = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal Admin 1600', 'login': 'pc.internal.1600@example.com',
            'group_ids': [Command.set([
                env.ref('base.group_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_admin').id,
            ])],
        })

    def _notes(self, patient):
        return patient.sudo().message_ids.filtered(
            lambda m: 'Identity correction confirmed by' in (m.body or ''))

    def _save(self, **data):
        payload = {'csrf_token': self._csrf(), 'patient_id': self.player.id}
        payload.update(data)
        return self.url_open('/my/player/save', data=payload, allow_redirects=False)


@tagged('-at_install', 'post_install')
class TestIdentityGuardModel1600(IdentityCommon):

    # ----- AC-d (model) -----
    def test_portal_change_needs_confirmation(self):
        with self.assertRaises(UserError):
            self.player.with_user(self.coach).write({'first_name': 'Changed'})
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Pat')
        with self.assertRaises(UserError):
            self.player.with_user(self.tp).write({'date_of_birth': '2008-03-05'})

    def test_portal_change_confirmed_is_recorded(self):
        self.player.with_user(self.tp).with_context(sc_identity_confirmed=True).write({
            'first_name': 'Patrice', 'date_of_birth': '2008-03-05'})
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Patrice')
        note = self._notes(self.player)
        self.assertEqual(len(note), 1)
        self.assertIn('PC TP', note.body)
        self.assertIn('Pat → Patrice', note.body)
        self.assertIn('2008-03-04 → 2008-03-05', note.body)
        self.assertEqual(note.author_id, self.tp.partner_id)

    def test_filling_a_blank_or_same_value_is_free(self):
        blank = self.env['sports.patient'].create({
            'first_name': 'Eli', 'last_name': 'Synthetic', 'team_ids': [Command.set([self.team_a.id])]})
        blank.with_user(self.tp).write({'date_of_birth': '2011-07-08'})
        self.assertEqual(str(blank.date_of_birth), '2011-07-08')
        # The same value (and whitespace-only differences) is not a change.
        self.player.with_user(self.coach).write({'first_name': ' Pat ', 'last_name': 'One'})
        self.assertFalse(self._notes(blank) | self._notes(self.player))

    def test_internal_user_unaffected(self):
        self.player.with_user(self.internal).write({'first_name': 'Backend'})
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Backend')
        self.assertFalse(self._notes(self.player))

    def test_internal_confirmed_correction_is_recorded(self):
        # Owner 2026-10-12: a clinic administrator who goes through the
        # portal confirm step gets the same note on the file.
        self.player.with_user(self.internal).with_context(sc_identity_confirmed=True).write(
            {'first_name': 'Patricia'})
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Patricia')
        note = self._notes(self.player)
        self.assertEqual(len(note), 1)
        self.assertIn('Pat → Patricia', note.body)
        self.assertEqual(note.author_id, self.internal.partner_id)

    # ----- AC-c (model) -----
    def test_duplicate_identity_refused_for_portal(self):
        writer = self.player.with_user(self.tp).with_context(sc_identity_confirmed=True)
        # Security review 2026-10-23: Dana is on another team (not readable):
        # the generic refusal, whatever the date of birth
        # (test_identity_oracle_1023).
        with self.assertRaisesRegex(ValidationError, 'A player with this identity already exists'):
            writer.write({'first_name': ' dana ', 'last_name': 'SYNTHETIC', 'date_of_birth': '2010-01-02'})
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Pat')
        # Archived files count too.
        self.other.active = False
        with self.assertRaises(ValidationError):
            writer.write({'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': '2010-01-02'})
        # Create through the portal path.
        with self.assertRaises(ValidationError):
            self.env['sports.patient'].with_user(self.tp).create_portal_patient({
                'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': '2010-01-02',
                'team_ids': [Command.set([self.team_a.id])]})
        # The same values on the same player are fine.
        self.other.with_user(self.tp).sudo().write({'first_name': 'Dana'})

    def test_duplicate_identity_allowed_internal(self):
        twin = self.env['sports.patient'].with_user(self.internal).create({
            'first_name': 'Dana', 'last_name': 'Synthetic', 'date_of_birth': '2010-01-02'})
        self.assertTrue(twin)


@tagged('-at_install', 'post_install')
class TestIdentityGuardLegacy1600(IdentityCommon):

    # ----- AC-d (legacy form) -----
    def test_legacy_rename_without_confirmation_refused(self):
        self._login_tp()
        resp = self._save(first_name='Patrice', last_name='One', team_ids=str(self.team_a.id))
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/my/player/edit', resp.headers['Location'])
        page = self.url_open(resp.headers['Location']).text
        self.assertIn('Confirm the identity correction', page)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Pat')

    def test_legacy_rename_confirmed(self):
        self._login_coach()
        resp = self._save(first_name='Patrice', last_name='One', identity_confirmed='1')
        self.assertEqual(resp.status_code, 303)
        self.assertNotIn('/my/player/edit', resp.headers['Location'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Patrice')
        self.assertEqual(len(self._notes(self.player)), 1)

    def test_legacy_unchanged_identity_needs_nothing(self):
        self._login_tp()
        resp = self._save(first_name='Pat', last_name='One', date_of_birth='2008-03-04',
                          position='Center', team_ids=str(self.team_a.id))
        self.assertNotIn('/my/player/edit', resp.headers['Location'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.position, 'Center')

    # ----- AC-c (legacy) -----
    @mute_logger('odoo.addons.bemade_sports_clinic.controllers.player_management_portal')
    def test_legacy_create_duplicate_refused(self):
        self._login_tp()
        partners = self.env['res.partner'].search_count([])
        resp = self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'DANA', 'last_name': 'synthetic',
            'date_of_birth': '2010-01-02', 'team_ids': str(self.team_a.id),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/my/player/create', resp.headers['Location'])
        # Security review 2026-10-23: Dana is on another team — the generic
        # refusal (test_identity_oracle_1023).
        self.assertIn('A player with this identity already exists — ask a manager.',
                      self.url_open('/my/player/create').text)
        self.assertEqual(self.env['res.partner'].search_count([]), partners,
                         "no orphan contact left behind")

    # ----- AC-b -----
    def test_refused_save_changes_nothing(self):
        self.player.team_ids = [Command.set([self.team_a.id, self.team_c.id])]
        self._login_tp()
        Patient = type(self.env['sports.patient'])

        def boom(self, *args, **kwargs):
            raise UserError("Synthetic failure after the write")

        with patch.object(Patient, 'remove_from_team', boom):
            resp = self._save(first_name='Pat', last_name='One', position='Rolledback',
                              team_ids=str(self.team_a.id))
        self.assertIn('/my/player/edit', resp.headers['Location'])
        self.player.invalidate_recordset()
        self.assertNotEqual(self.player.position, 'Rolledback')
        self.assertEqual(self.player.team_ids, self.team_a | self.team_c)

    # ----- AC-f -----
    def test_untick_team_is_official_removal(self):
        self.player.team_ids = [Command.set([self.team_a.id, self.team_b.id, self.team_c.id])]
        self.player.pending_removal = True
        activity = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Player Removal Request', 'user_id': self.tp.id,
        })
        self._login_tp()
        resp = self._save(first_name='Pat', last_name='One', team_ids=str(self.team_a.id))
        self.assertEqual(resp.status_code, 303)
        self.assertNotIn('/my/player/edit', resp.headers['Location'])
        self.player.invalidate_recordset()
        # Team C (the therapist's) removed; team B (not theirs) kept.
        self.assertEqual(self.player.team_ids, self.team_a | self.team_b)
        self.assertFalse(self.player.pending_removal)
        self.assertFalse(activity.exists() and activity.active)
        bodies = ' '.join(self.player.sudo().message_ids.mapped('body'))
        self.assertIn('removed from team PC Team C 1600', bodies)
        self.assertIn('Pending removal flag was cleared', bodies)

    def test_untick_last_team_lands_on_players(self):
        self._login_tp()
        resp = self._save(first_name='Pat', last_name='One')  # no team ticked
        self.assertEqual(resp.status_code, 303)
        self.assertTrue(resp.headers['Location'].endswith('/my/players'), resp.headers['Location'])
        self.assertEqual(self.url_open(resp.headers['Location']).status_code, 200)
        self.player.invalidate_recordset()
        self.assertFalse(self.player.sudo().team_ids)
        # No flash left behind: the next form opened shows no error.
        other = self.env['sports.patient'].create({
            'first_name': 'Fay', 'last_name': 'Synthetic', 'team_ids': [Command.set([self.team_c.id])]})
        page = self.url_open('/my/player/edit?patient_id=%s' % other.id).text
        self.assertNotIn('class="alert alert-danger"', page)


@tagged('-at_install', 'post_install')
class TestIdentityGuardAppShell1600(IdentityCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(SWITCH, 'True')

    def _app_save(self, field, value, **extra):
        self.player.invalidate_recordset()
        data = {'field': field, 'value': value, 'csrf_token': self._csrf(),
                'write_date': fields.Datetime.to_string(self.player.write_date)}
        data.update(extra)
        return self.url_open('/my/app/save/sports.patient/%s' % self.player.id, data=data,
                             allow_redirects=False)

    # ----- AC-e -----
    def test_pencil_rename_needs_confirm(self):
        self._login_tp()
        resp = self._app_save('last_name', 'Onesynth')
        self.assertEqual(resp.status_code, 428, resp.text)
        body = resp.json()
        self.assertTrue(body['confirm_identity'])
        self.assertEqual((body['old'], body['new']), ('One', 'Onesynth'))
        self.player.invalidate_recordset()
        self.assertEqual(self.player.last_name, 'One')
        resp = self._app_save('last_name', 'Onesynth', confirm='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.last_name, 'Onesynth')
        self.assertEqual(len(self._notes(self.player)), 1)

    def test_pencil_dob_change_and_fill(self):
        self._login_tp()
        self.assertEqual(self._app_save('date_of_birth', '2008-04-04').status_code, 428)
        self.assertEqual(self._app_save('date_of_birth', '2008-04-04', confirm='1').status_code, 200)
        blank = self.env['sports.patient'].create({
            'first_name': 'Gus', 'last_name': 'Synthetic', 'team_ids': [Command.set([self.team_a.id])]})
        resp = self.url_open('/my/app/save/sports.patient/%s' % blank.id, data={
            'field': 'date_of_birth', 'value': '2012-02-03', 'csrf_token': self._csrf(),
            'write_date': fields.Datetime.to_string(blank.write_date)}, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_pencil_admin_confirms_too(self):
        # Same confirm step for every user (owner 2026-10-12), and the
        # administrator's confirmed correction is recorded on the file.
        self.internal.password = 'pc-internal-1600'
        self.authenticate('pc.internal.1600@example.com', 'pc-internal-1600')
        resp = self._app_save('first_name', 'Patsy')
        self.assertEqual(resp.status_code, 428, resp.text)
        resp = self._app_save('first_name', 'Patsy', confirm='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(self.player.first_name, 'Patsy')
        self.assertEqual(len(self._notes(self.player)), 1)

    def test_pencil_duplicate_refused(self):
        self.player.write({'first_name': 'Dana', 'date_of_birth': '2010-01-02'})
        self._login_tp()
        resp = self._app_save('last_name', 'Synthetic', confirm='1')
        self.assertEqual(resp.status_code, 400, resp.text)
        # Security review 2026-10-23: Dana is on another team — the generic
        # refusal (test_identity_oracle_1023).
        self.assertIn('A player with this identity already exists', resp.json()['message'])


@tagged('-at_install', 'post_install')
class TestRemovalCleanupMigration1600(IdentityCommon):

    def _removal_activity(self, patient, summary='Player Removal Request'):
        return self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': patient.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': summary, 'user_id': self.tp.id,
        })

    # ----- AC-g -----
    def test_migration_closes_only_teamless_pending(self):
        Patient = self.env['sports.patient']
        teamless = Patient.create({'first_name': 'Hal', 'last_name': 'Synthetic', 'pending_removal': True})
        archived = Patient.create({'first_name': 'Ivy', 'last_name': 'Synthetic', 'pending_removal': True})
        archived.active = False
        teamed = Patient.create({'first_name': 'Jo', 'last_name': 'Synthetic', 'pending_removal': True,
                                 'team_ids': [Command.set([self.team_a.id])]})
        acts = {
            'teamless': self._removal_activity(teamless),
            'archived': self._removal_activity(archived, 'Demande de suppression de joueur: Ivy'),
            'teamed': self._removal_activity(teamed),
        }
        other_task = self._removal_activity(teamless, 'Call the parents')

        migration = _load_migration()
        with patch.object(migration, '_logger') as logger:
            migration.migrate(self.env.cr, '19.0.1.59.0')
        args = logger.info.call_args.args
        self.assertEqual(args[1:], (2, 2), "2 players cleared, 2 requests closed (logged)")

        for patient in (teamless, archived, teamed):
            patient.invalidate_recordset()
        self.assertFalse(teamless.pending_removal)
        self.assertFalse(archived.pending_removal)
        self.assertTrue(teamed.pending_removal)
        Activity = self.env['mail.activity']
        self.assertFalse(Activity.search([('id', '=', acts['teamless'].id)]))
        self.assertFalse(Activity.search([('id', '=', acts['archived'].id)]))
        self.assertTrue(Activity.search([('id', '=', acts['teamed'].id)]))
        self.assertTrue(Activity.search([('id', '=', other_task.id)]), "other activities untouched")
        feedback = ' '.join(teamless.sudo().message_ids.mapped('body'))
        self.assertIn('Closed: the player is no longer on the team.', feedback)
