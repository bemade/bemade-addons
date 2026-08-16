"""Team-dashboard rollup coverage (task 1272).

Acceptance criteria exercised here (server-side logic only; the portal tab and
backend page UI are verified separately by /dev-review click-through):

  AC2  Recency domain + score ranking: recently-active players surface, ordered
       by the role score; players whose activity aged past the window drop out.
  AC3  Role isolation (Law 25): an internal-note change or a hidden-from-coaches
       injury updates ONLY the TP rollups — a coach never sees it, not even as a
       count.
  AC4  Three-way team-health stage counts (no_play / practice_ok / healthy).
  AC6  On-change propagation with no cron: creating an injury, changing
       play-status, or editing a note bumps the correct role stamp(s)+score(s)
       immediately.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTeamDashboard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Acting as admin (base.group_system): injuries created here land 'active'
        # and, per the module, admin counts as a treatment professional.
        cls.tp_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]

        cls.org = cls.env['res.partner'].create(
            {'name': 'Dash Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create(
            {'name': 'Dash Team', 'parent_id': cls.org.id})

    # ------------------------------------------------------------------ helpers
    def _patient(self, first='Test', last='Player', team=True, **vals):
        vals.setdefault('first_name', first)
        vals.setdefault('last_name', last)
        if team:
            vals['team_ids'] = [Command.link(self.team.id)]
        return self.env['sports.patient'].create(vals)

    def _injury(self, patient, **vals):
        vals['patient_id'] = patient.id
        return self.env['sports.patient.injury'].create(vals)

    def _cutoff(self):
        return self.env['sports.patient']._dashboard_window_cutoff()

    def _force_coach_stamp(self, patient, when, note_count=0):
        """Directly set the coach rollup (bypassing propagation) to a known
        baseline, so a later assertion can prove it was/was not touched."""
        patient.sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_coach': when,
            'dashboard_note_update_count_coach': note_count,
        })

    # ------------------------------------------------------------------- AC6
    def test_new_injury_bumps_both_roles(self):
        patient = self._patient()
        self.assertFalse(patient.dashboard_last_activity_coach)
        self.assertFalse(patient.dashboard_last_activity_tp)

        self._injury(patient, diagnosis='Sprain')
        patient.invalidate_recordset()

        cutoff = self._cutoff()
        self.assertTrue(patient.dashboard_last_activity_coach >= cutoff)
        self.assertTrue(patient.dashboard_last_activity_tp >= cutoff)
        self.assertEqual(patient.dashboard_new_injury_count_coach, 1)
        self.assertEqual(patient.dashboard_new_injury_count_tp, 1)
        self.assertTrue(patient.dashboard_score_tp > 0)

    def test_play_status_change_bumps_both_roles(self):
        patient = self._patient()
        self._force_coach_stamp(patient, fields.Datetime.now() - timedelta(hours=48))

        patient.write({'match_status': 'no', 'practice_status': 'no'})
        patient.invalidate_recordset()

        cutoff = self._cutoff()
        self.assertEqual(patient.stage, 'no_play')
        self.assertTrue(patient.dashboard_last_activity_coach >= cutoff)
        self.assertTrue(patient.dashboard_last_activity_tp >= cutoff)
        # no_play weight (3) dominates the score.
        self.assertEqual(patient.dashboard_score_coach, 3000)
        self.assertEqual(patient.dashboard_score_tp, 3000)

    def test_external_note_bumps_both_roles(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis='Bruise')
        past = fields.Datetime.now() - timedelta(hours=48)
        self._force_coach_stamp(patient, past)

        injury.write({'external_notes': 'Visible to the coach.'})
        patient.invalidate_recordset()

        cutoff = self._cutoff()
        # External notes are coach-visible -> coach stamp refreshed off baseline.
        self.assertTrue(patient.dashboard_last_activity_coach >= cutoff)
        self.assertTrue(patient.dashboard_last_activity_tp >= cutoff)
        self.assertEqual(patient.dashboard_note_update_count_coach, 1)
        self.assertEqual(patient.dashboard_note_update_count_tp, 1)

    # ------------------------------------------------------------------- AC3
    def test_internal_note_does_not_bump_coach(self):
        """The load-bearing Law 25 test: an internal-note change updates ONLY
        the TP rollups; the coach rollups are left exactly as they were."""
        patient = self._patient()
        injury = self._injury(patient, diagnosis='ACL')
        # Freeze a known coach baseline AFTER the (coach-visible) new injury.
        past = fields.Datetime.now() - timedelta(hours=48)
        self._force_coach_stamp(patient, past, note_count=0)

        injury.write({'internal_notes': 'Confidential clinical detail.'})
        patient.invalidate_recordset()

        # Coach rollup untouched — not even the count.
        self.assertEqual(patient.dashboard_last_activity_coach, past)
        self.assertEqual(patient.dashboard_note_update_count_coach, 0)
        # TP rollup did register the internal note.
        self.assertTrue(patient.dashboard_last_activity_tp >= self._cutoff())
        self.assertEqual(patient.dashboard_note_update_count_tp, 1)

    def test_hidden_injury_bumps_tp_only(self):
        patient = self._patient()
        self._injury(patient, diagnosis='Hidden', hidden_from_coaches=True)
        patient.invalidate_recordset()

        # Coach never learns a hidden injury exists.
        self.assertFalse(patient.dashboard_last_activity_coach)
        self.assertEqual(patient.dashboard_new_injury_count_coach, 0)
        # TP sees it.
        self.assertTrue(patient.dashboard_last_activity_tp >= self._cutoff())
        self.assertEqual(patient.dashboard_new_injury_count_tp, 1)

    def test_internal_note_on_hidden_injury_stays_tp_only(self):
        patient = self._patient()
        injury = self._injury(patient, diagnosis='Hidden', hidden_from_coaches=True)
        past = fields.Datetime.now() - timedelta(hours=48)
        self._force_coach_stamp(patient, past, note_count=0)

        # Even an *external* note on a hidden injury must not reach the coach.
        injury.write({'external_notes': 'Still hidden from the coach.'})
        patient.invalidate_recordset()

        self.assertEqual(patient.dashboard_last_activity_coach, past)
        self.assertEqual(patient.dashboard_note_update_count_coach, 0)
        self.assertEqual(patient.dashboard_note_update_count_tp, 1)

    # ------------------------------------------------------------------- AC4
    def test_three_way_stage_counts(self):
        healthy = self._patient('H', 'One')
        practice = self._patient(
            'P', 'Two', match_status='no', practice_status='yes')
        no_play = self._patient(
            'N', 'Three', match_status='no', practice_status='no')
        self.team.invalidate_recordset()

        self.assertEqual(healthy.stage, 'healthy')
        self.assertEqual(practice.stage, 'practice_ok')
        self.assertEqual(no_play.stage, 'no_play')
        self.assertEqual(self.team.stage_healthy_count, 1)
        self.assertEqual(self.team.stage_practice_ok_count, 1)
        self.assertEqual(self.team.stage_no_play_count, 1)

    # ------------------------------------------------------------------- AC2
    def test_recency_domain_drops_stale_players(self):
        patient = self._patient()
        self._injury(patient, diagnosis='Recent')
        self.team.invalidate_recordset()
        self.assertIn(patient, self.team.dashboard_active_patient_ids)

        # Age the TP activity past the window -> the player drops off.
        patient.sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_tp': fields.Datetime.now() - timedelta(hours=48),
        })
        self.team.invalidate_recordset()
        self.assertNotIn(patient, self.team.dashboard_active_patient_ids)

    def test_active_players_ranked_by_score_desc(self):
        # A no_play player (stage weight 3) must outrank a healthy player whose
        # only activity is a note update.
        urgent = self._patient(
            'Urgent', 'Case', match_status='no', practice_status='no')
        self._injury(urgent, diagnosis='Severe')
        minor = self._patient('Minor', 'Case')
        inj = self._injury(minor, diagnosis='Minor')
        inj.write({'external_notes': 'note'})
        self.team.invalidate_recordset()

        ranked = self.team.dashboard_active_patient_ids
        self.assertIn(urgent, ranked)
        self.assertIn(minor, ranked)
        self.assertLess(
            list(ranked).index(urgent), list(ranked).index(minor),
            "The no_play player must rank ahead of the healthy one.")
        self.assertGreater(urgent.dashboard_score_tp, minor.dashboard_score_tp)

    def test_window_hours_config_parameter(self):
        Patient = self.env['sports.patient']
        self.assertEqual(Patient._dashboard_window_hours(), 24)
        self.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.dashboard_activity_window_hours', '72')
        self.assertEqual(Patient._dashboard_window_hours(), 72)
        # Invalid values fall back to the 24h default.
        self.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.dashboard_activity_window_hours', 'abc')
        self.assertEqual(Patient._dashboard_window_hours(), 24)

    # ---------------------------------- task 1392: Settings get/set + floor guard
    def test_settings_window_get_set_and_floor(self):
        """The Settings field round-trips the param and floors it at 1h so a
        zero/negative value can never be persisted."""
        Settings = self.env['res.config.settings']
        ICP = self.env['ir.config_parameter'].sudo()
        Patient = self.env['sports.patient']

        # Default surfaces as 24 when the param is unset.
        self.assertEqual(Settings.create({}).dashboard_activity_window_hours, 24)

        # Saving a valid value writes the param.
        Settings.create(
            {'dashboard_activity_window_hours': 72}).execute()
        self.assertEqual(
            ICP.get_param('bemade_sports_clinic.dashboard_activity_window_hours'),
            '72')
        self.assertEqual(Patient._dashboard_window_hours(), 72)

        # Zero floors to 1 (never persisted as <=0).
        Settings.create(
            {'dashboard_activity_window_hours': 0}).execute()
        self.assertEqual(
            int(ICP.get_param(
                'bemade_sports_clinic.dashboard_activity_window_hours')), 1)
        self.assertEqual(Patient._dashboard_window_hours(), 1)

        # Negative floors to 1 as well.
        Settings.create(
            {'dashboard_activity_window_hours': -5}).execute()
        self.assertEqual(
            int(ICP.get_param(
                'bemade_sports_clinic.dashboard_activity_window_hours')), 1)
        self.assertEqual(Patient._dashboard_window_hours(), 1)
