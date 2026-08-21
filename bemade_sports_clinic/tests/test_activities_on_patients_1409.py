"""Task 1409 — activities live on PATIENTS only.

Acceptance criteria (plan 1409):
1. Portal: no way to create/list activities ON an injury (injury card, injury
   edit page, create form, activities list filters, direct
   ``/my/activity/create?model=sports.patient.injury`` -> redirect); patient
   activities work exactly as before; the player page Activities tab lists
   the migrated ones with the « [Injury: …] » prefix.
2. After upgrade: 0 mail.activity on sports.patient.injury, every former
   injury activity moved to its patient with ``injury_id`` set and the prefix
   once; digest ``pending_verify`` unchanged; « Vérifier » still closes its
   To-Do; the cron creates new To-Dos on the patient with ``injury_id``.
3. Backend injury form/list unchanged (not covered here — view untouched).
4. Full suite green; fr_CA verified.

The removed buttons/badges, the redirect landing and the player page tab are
browser behaviour — NOT verified here beyond the rendered HTML; see the
dev-review UAT walkthrough. All fixtures are synthetic (public repo).
"""
import importlib.util
import os

from odoo import fields
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestActivitiesOnPatients1409(PortalCovCommon):

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _load_migration(self):
        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(module_root, 'migrations', '19.0.1.26.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_26_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _injury_scoped_activity(self, summary, injury=None, user=None):
        """A LEGACY activity scheduled ON the injury (what the backend chatter
        still allows; what prod carried before the migration)."""
        injury = injury or self.injury
        return self.env['mail.activity'].sudo().create({
            'res_model_id': self.env['ir.model']._get('sports.patient.injury').id,
            'res_id': injury.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': summary,
            'user_id': (user or self.tp).id,
            'date_deadline': fields.Date.today(),
        })

    # ------------------------------------------------------------------
    # AC2 — migration
    # ------------------------------------------------------------------
    def test_migration_moves_injury_activities_to_patient_prefixed_once(self):
        legacy = self._injury_scoped_activity('Call about brace')
        already = self._injury_scoped_activity('[Blessure : Sprain] Deja prefixee')
        before_patient = self.act_player.summary
        before_count_on_patient = self.env['mail.activity'].sudo().search_count(
            [('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id)])
        self.env.flush_all()

        self._load_migration().migrate(self.env.cr, '19.0.1.25.4')
        self.env.invalidate_all()

        self.assertFalse(self.env['mail.activity'].sudo().search(
            [('res_model', '=', 'sports.patient.injury')]),
            "no activity may remain on an injury after the migration")
        for act in (legacy, already):
            self.assertEqual(act.res_model, 'sports.patient')
            self.assertEqual(act.res_model_id.model, 'sports.patient')
            self.assertEqual(act.res_id, self.player.id)
            self.assertEqual(act.injury_id, self.injury)
        self.assertEqual(legacy.summary, '[Blessure : Sprain] Call about brace',
                         "the prefix carries the injury diagnosis")
        self.assertEqual(already.summary, '[Blessure : Sprain] Deja prefixee',
                         "an already-prefixed summary is not prefixed twice")
        # Pre-existing patient activities are untouched.
        self.assertEqual(self.act_player.summary, before_patient)
        self.assertFalse(self.act_player.injury_id)
        self.assertEqual(
            self.env['mail.activity'].sudo().search_count(
                [('res_model', '=', 'sports.patient'), ('res_id', '=', self.player.id)]),
            before_count_on_patient + 2)

        # Idempotent: a second run is a no-op.
        self._load_migration().migrate(self.env.cr, '19.0.1.25.4')
        self.env.invalidate_all()
        self.assertEqual(legacy.summary, '[Blessure : Sprain] Call about brace')

    def test_migration_moved_rows_show_on_player_tab(self):
        legacy = self._injury_scoped_activity('MigratedInjuryTask1409')
        self.env.flush_all()
        self._load_migration().migrate(self.env.cr, '19.0.1.25.4')
        self.env.invalidate_all()
        self._login_tp()
        resp = self.url_open(f'/my/player?player_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('[Blessure : Sprain] MigratedInjuryTask1409', resp.text)
        self.assertIn(f'/my/activity/{legacy.id}', resp.text)

    # ------------------------------------------------------------------
    # AC2 — digest pending_verify keyed on injury_id
    # ------------------------------------------------------------------
    def test_digest_pending_verify_counts_patient_todo_by_injury_link(self):
        Users = self.env['res.users']
        base = Users._digest_pending_verify_count(self.team_a)
        todo = self.env['mail.activity'].sudo().create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id,
            'injury_id': self.injury.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': '[Injury: Sprain] Verify injury',
            'user_id': self.tp.id,
            'date_deadline': fields.Date.today(),
        })
        self.assertEqual(Users._digest_pending_verify_count(self.team_a), base + 1)
        # Team B has no injury -> unchanged.
        self.assertEqual(Users._digest_pending_verify_count(self.team_b), 0)
        # A patient To-Do WITHOUT the injury link is not a verification.
        self.env['mail.activity'].sudo().create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Verify injury',
            'user_id': self.tp.id,
            'date_deadline': fields.Date.today(),
        })
        self.assertEqual(Users._digest_pending_verify_count(self.team_a), base + 1)
        todo.unlink()
        self.assertEqual(Users._digest_pending_verify_count(self.team_a), base)

    # ------------------------------------------------------------------
    # AC1 — portal surface
    # ------------------------------------------------------------------
    def test_create_form_rejects_injury_model(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/activity/create?model=sports.patient.injury&res_id={self.injury.id}',
            allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/my/activities', resp.headers.get('Location', ''))

    def test_save_post_rejects_injury_model(self):
        self._login_tp()
        resp = self.url_open('/my/activity/save', data={
            'csrf_token': self._csrf(),
            'model': 'sports.patient.injury',
            'res_id': self.injury.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'ForgedInjuryActivity1409',
            'user_id': self.tp.id,
            'date_deadline': fields.Date.today().strftime('%Y-%m-%d'),
        })
        self.assertIn(resp.status_code, (200, 302))
        self.assertFalse(self.env['mail.activity'].sudo().search(
            [('summary', '=', 'ForgedInjuryActivity1409')]),
            "a forged injury-target POST must not create anything")

    def test_activities_list_has_no_injury_branch(self):
        """A backend-scheduled activity ON an injury never surfaces in the
        portal list; the injury-model filter is empty; patient activities
        (incl. the injury-prefixed one) list as before."""
        self._injury_scoped_activity('LegacyInjuryOnly1409')
        self._login_tp()
        resp = self.url_open('/my/activities?model=sports.patient.injury')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('LegacyInjuryOnly1409', resp.text)
        self.assertNotIn('Injury task', resp.text)
        resp = self.url_open(
            f'/my/activities?model=sports.patient&res_id={self.player.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('[Injury: Sprain] Injury task', resp.text)
        self.assertNotIn('LegacyInjuryOnly1409', resp.text)
        # The injury-prefixed activity's detail page renders (patient context).
        resp = self.url_open(f'/my/activity/{self.act_injury.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('[Injury: Sprain] Injury task', resp.text)
        self.assertNotIn('/my/injury/activities', resp.text)

    def test_injury_activities_route_redirect_keeps_team_context(self):
        self._login_tp()
        resp = self.url_open(
            f'/my/injury/activities?injury_id={self.injury.id}&team_id={self.team_a.id}',
            allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        location = resp.headers.get('Location', '')
        self.assertIn(f'/my/player?player_id={self.player.id}', location)
        self.assertIn(f'team_id={self.team_a.id}', location)
        self.assertIn('#activities', location)
