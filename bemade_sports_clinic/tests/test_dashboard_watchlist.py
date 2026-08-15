"""Portal-dashboard watchlist coverage (task 1382, digest epic).

`sports.team.dashboard_watchlist_patient_ids` lists the red (no_play) + yellow
(practice_ok) players who are NOT already in the recent-changes set
(`dashboard_active_patient_ids`), ordered red -> yellow then alpha, so at-risk
players with no recent change stay visible below the recent-changes list on the
portal dashboard.

Acceptance criteria exercised here (server-side logic only; the collapsed
`<details>` section render is verified separately by /dev-review click-through):

  AC1  The watchlist is exactly the red/yellow players NOT in the active set.
  AC2  Green (healthy) players never appear, active or not.
  AC3  Order is red -> yellow (sort_order), alpha within a stage.
  AC4  Set difference is correct: no player is in both the active set and the
       watchlist.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestDashboardWatchlist(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp_group = cls.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        cls.env.user.sudo().group_ids = [Command.link(cls.tp_group.id)]

        cls.org = cls.env['res.partner'].create(
            {'name': 'Watch Org', 'is_company': True})
        cls.team = cls.env['sports.team'].create(
            {'name': 'Watch Team', 'parent_id': cls.org.id})

    # ------------------------------------------------------------------ helpers
    def _player(self, first, last, stage, active):
        """Create a team player pinned to a stage and an active/inactive state.

        stage: 'no_play' (red) | 'practice_ok' (yellow) | 'healthy' (green).
        active: True -> in the recent-changes set (recent tp activity);
                False -> not in it (activity stamp cleared).
        """
        status = {
            'no_play': {'match_status': 'no', 'practice_status': 'no'},
            'practice_ok': {'match_status': 'no', 'practice_status': 'yes'},
            'healthy': {'match_status': 'yes', 'practice_status': 'yes'},
        }[stage]
        patient = self.env['sports.patient'].create({
            'first_name': first,
            'last_name': last,
            'team_ids': [Command.link(self.team.id)],
            **status,
        })
        self.assertEqual(patient.stage, stage)
        # Pin membership in the active (recent-changes) set explicitly, so the
        # test does not depend on how create-time propagation stamped activity.
        when = (
            fields.Datetime.now() if active
            else fields.Datetime.now() - timedelta(hours=72)
        )
        patient.sudo().with_context(dashboard_bump=True).write({
            'dashboard_last_activity_tp': when,
        })
        return patient

    def _watchlist(self):
        self.team.invalidate_recordset()
        return self.team.dashboard_watchlist_patient_ids

    def _active(self):
        self.team.invalidate_recordset()
        return self.team.dashboard_active_patient_ids

    # ------------------------------------------------------------------- AC1/AC2
    def test_watchlist_is_red_yellow_minus_active(self):
        red_idle = self._player('Rob', 'Alpha', 'no_play', active=False)
        red_active = self._player('Rex', 'Bravo', 'no_play', active=True)
        yellow_idle = self._player('Yan', 'Charlie', 'practice_ok', active=False)
        yellow_active = self._player('Yves', 'Delta', 'practice_ok', active=True)
        green_idle = self._player('Gil', 'Echo', 'healthy', active=False)
        green_active = self._player('Guy', 'Foxtrot', 'healthy', active=True)

        watchlist = self._watchlist()

        # Only the idle red + idle yellow qualify.
        self.assertIn(red_idle, watchlist)
        self.assertIn(yellow_idle, watchlist)
        # Active red/yellow are in the recent-changes set instead.
        self.assertNotIn(red_active, watchlist)
        self.assertNotIn(yellow_active, watchlist)
        # Green never appears, active or not.
        self.assertNotIn(green_idle, watchlist)
        self.assertNotIn(green_active, watchlist)
        self.assertEqual(watchlist, red_idle + yellow_idle)

    # ----------------------------------------------------------------------- AC3
    def test_watchlist_order_red_then_yellow_then_alpha(self):
        # Deliberately create out of order to prove the sort, not insertion.
        y_aaron = self._player('Ann', 'Aaron', 'practice_ok', active=False)
        r_beta = self._player('Ben', 'Beta', 'no_play', active=False)
        r_alpha = self._player('Amy', 'Alpha', 'no_play', active=False)
        y_baker = self._player('Bo', 'Baker', 'practice_ok', active=False)

        watchlist = self._watchlist()
        # Reds first (alpha: Alpha, Beta), then yellows (alpha: Aaron, Baker).
        self.assertEqual(watchlist, r_alpha + r_beta + y_aaron + y_baker)

    # ----------------------------------------------------------------------- AC4
    def test_no_player_in_both_active_and_watchlist(self):
        self._player('Rob', 'Alpha', 'no_play', active=False)
        self._player('Rex', 'Bravo', 'no_play', active=True)
        self._player('Yan', 'Charlie', 'practice_ok', active=False)
        self._player('Yves', 'Delta', 'practice_ok', active=True)

        overlap = self._active() & self._watchlist()
        self.assertFalse(
            overlap,
            "No player may appear in both the recent-changes set and the "
            "watchlist (set difference must be exact).",
        )
