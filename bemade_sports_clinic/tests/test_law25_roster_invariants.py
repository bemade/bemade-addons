"""Roster invariant for the Law 25 retention clock.

One invariant must hold on EVERY path that changes a player's roster, not just
the patient-side write it was originally hooked on:

I1  teamless <=> date_left_last_team set. The Law 25 retention rule keys on this
    date. A NULL clock never surfaces for anonymization (the record is kept
    forever); a stale clock ages the record out years early. Both are compliance
    failures, in opposite directions.

Our code does NOT archive players. Auto-archiving teamless players was tried and
dropped (owner, 2026-07-16): local UAT on a copy of prod showed it would archive
367 active teamless players — last season's rosters awaiting fall re-rostering,
not departed players. Archiving stays a manual action plus the Law 25
anonymization. These tests therefore assert that removal keeps the clock correct
and archives NO ONE.

Every test here drives a REAL removal path -- team.write, team.create,
team.unlink, patient.write, remove_from_team. None of them call an enforcement
helper directly.

Fixtures are synthetic throughout: invented names, no real player data.
"""

import importlib.util
import os

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestLaw25RosterInvariants(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({
            'name': 'Invariants Org', 'is_company': True,
        })
        cls.team = cls.env['sports.team'].create({
            'name': 'Invariants Team A', 'parent_id': cls.org.id,
        })
        cls.other_team = cls.env['sports.team'].create({
            'name': 'Invariants Team B', 'parent_id': cls.org.id,
        })

    def _player(self, teams=None, **vals):
        """A synthetic player, on ``teams`` by default."""
        vals.setdefault('first_name', 'Rostered')
        vals.setdefault('last_name', 'Player')
        if teams is not None:
            vals['team_ids'] = [Command.set(teams.ids)]
        return self.env['sports.patient'].create(vals)

    def _today(self):
        return fields.Date.context_today(self.env['sports.patient'])

    def _rel_rows(self, player):
        self.env.cr.execute(
            "SELECT team_id FROM sports_team_patient_rel WHERE patient_id = %s",
            (player.id,),
        )
        return [row[0] for row in self.env.cr.fetchall()]

    # ------------------------------------------------------------------
    # I1 -- the Law 25 retention clock, driven from the TEAM side
    # ------------------------------------------------------------------

    def test_i1_team_write_remove_stamps_clock(self):
        """AC6: team-side removal stamps the clock (it used to leave it NULL,
        so the player never surfaced to the retention rule)."""
        player = self._player(teams=self.team)
        self.assertFalse(player.date_left_last_team)

        self.team.write({'patient_ids': [Command.unlink(player.id)]})

        self.assertEqual(player.date_left_last_team, self._today())

    def test_i1_team_write_add_clears_stale_clock(self):
        """AC6: a team-side ADD clears a stale clock."""
        player = self._player()  # created teamless -> clock stamped
        self.assertEqual(player.date_left_last_team, self._today())

        self.team.write({'patient_ids': [Command.link(player.id)]})

        self.assertFalse(
            player.date_left_last_team,
            "Rejoining a team must clear the retention clock",
        )

    def test_i1_team_create_with_players_clears_stale_clock(self):
        """AC6: team.create carrying patient_ids clears a stale clock too."""
        player = self._player()
        self.assertEqual(player.date_left_last_team, self._today())

        self.env['sports.team'].create({
            'name': 'Invariants Team C',
            'parent_id': self.org.id,
            'patient_ids': [Command.set(player.ids)],
        })

        self.assertFalse(player.date_left_last_team)

    def test_i1_team_unlink_stamps_clock(self):
        """AC6/AC12: deleting a team stamps the clock for players left teamless."""
        team = self.env['sports.team'].create({
            'name': 'Invariants Team D', 'parent_id': self.org.id,
        })
        player = self._player(teams=team)
        self.assertFalse(player.date_left_last_team)

        team.unlink()

        self.assertEqual(player.date_left_last_team, self._today())

    def test_i1_early_anonymization_regression(self):
        """AC7: a stale clock must not survive a team-side rejoin.

        The original bug: team-side ADD left date_left_last_team set. When the
        player later left patient-side, the sync took neither branch (the date
        was already set), so the stale date stood as authoritative and the record
        was eligible for irreversible anonymization years early.
        """
        player = self._player()  # teamless, clock = today
        # Force a genuinely old clock, as if they had left long ago.
        player.date_left_last_team = '2020-01-01'

        # Team-side rejoin must clear the stale date...
        self.team.write({'patient_ids': [Command.link(player.id)]})
        self.assertFalse(
            player.date_left_last_team,
            "The team-side rejoin must clear the stale clock, not keep it",
        )

        # ...so that a later patient-side leave stamps the REAL leave date.
        player.write({'team_ids': [Command.clear()]})
        self.assertEqual(
            player.date_left_last_team,
            self._today(),
            "The clock must reflect the real leave date, not the stale one",
        )
        self.assertNotEqual(str(player.date_left_last_team), '2020-01-01')

    # ------------------------------------------------------------------
    # No auto-archiving -- removal keeps the clock, never archives
    # ------------------------------------------------------------------

    def test_remove_from_last_team_stamps_clock_but_does_not_archive(self):
        """AC8: dropped auto-archive. Removing a player's last team stamps the
        retention clock and leaves them ACTIVE. Driven by a real removal."""
        player = self._player(teams=self.team)
        self.assertTrue(player.active)

        player.remove_from_team(self.team.id)

        self.assertFalse(player.team_ids)
        self.assertEqual(player.date_left_last_team, self._today())
        self.assertTrue(player.active, "Removal must not archive the player")

    def test_remove_with_another_team_leaves_clock_null(self):
        """AC9: still on another team => still active, clock still NULL."""
        player = self._player(teams=self.team | self.other_team)

        player.remove_from_team(self.team.id)

        self.assertTrue(player.active)
        self.assertFalse(player.date_left_last_team)
        self.assertEqual(player.team_ids, self.other_team)

    def test_team_side_unlink_does_not_archive(self):
        """AC10: the per-row 'x' on the team form stamps the clock, never archives."""
        player = self._player(teams=self.team)
        self.assertTrue(player.active)

        self.team.write({'patient_ids': [Command.unlink(player.id)]})

        self.assertTrue(player.active)
        self.assertEqual(player.date_left_last_team, self._today())

    def test_direct_patient_write_does_not_archive(self):
        """AC11: patient.write({'team_ids': [Command.clear()]}) stamps, no archive."""
        player = self._player(teams=self.team)
        self.assertTrue(player.active)

        player.write({'team_ids': [Command.clear()]})

        self.assertTrue(player.active)
        self.assertEqual(player.date_left_last_team, self._today())

    def test_team_unlink_does_not_archive(self):
        """AC12: deleting a team stamps the clock but does not archive players."""
        team = self.env['sports.team'].create({
            'name': 'Invariants Team E', 'parent_id': self.org.id,
        })
        stays = self._player(teams=team | self.other_team)
        goes = self._player(teams=team)
        self.assertTrue(goes.active)

        team.unlink()

        self.assertTrue(goes.active, "Team deletion must not archive")
        self.assertEqual(goes.date_left_last_team, self._today())
        self.assertTrue(stays.active)
        self.assertFalse(stays.date_left_last_team)

    def test_create_teamless_stamps_clock_and_stays_active(self):
        """A player created without a team gets a clock and stays active."""
        player = self._player()

        self.assertTrue(player.active, "Creation must not archive")
        self.assertEqual(player.date_left_last_team, self._today(),
                         "...but the retention clock still starts")

    # ------------------------------------------------------------------
    # Archived players may be rostered -- the team-side guard is gone
    # ------------------------------------------------------------------

    def test_archived_player_allowed_on_roster(self):
        """The old I3 team-side guard is dropped: an archived player on a roster
        is now an allowed state. Linking one must NOT raise, and their clock
        clears because they now have a team."""
        archived = self._player()
        archived.write({'active': False})
        self.assertFalse(archived.active)

        # No ValidationError -- the guard is gone.
        self.team.write({'patient_ids': [Command.link(archived.id)]})

        self.assertIn(
            archived,
            self.team.with_context(active_test=False).patient_ids,
            "Archived players are allowed on the roster now",
        )
        self.assertFalse(
            archived.date_left_last_team,
            "Having a team clears the retention clock even when archived",
        )
        self.assertFalse(archived.active, "Linking must not silently reactivate")

    def test_archiving_a_player_leaves_them_rostered(self):
        """Archiving no longer clears team_ids: the I3 write-hook is dropped."""
        player = self._player(teams=self.team | self.other_team)
        self.assertTrue(self._rel_rows(player))

        player.write({'active': False})

        self.assertFalse(player.active)
        self.assertEqual(
            sorted(self._rel_rows(player)),
            sorted((self.team | self.other_team).ids),
            "Archiving a player must leave their roster untouched",
        )

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def _load_migration(self):
        module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(module_root, 'migrations', '19.0.1.7.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('bsc_migration_19_0_1_7_0', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_migration_stamps_clockless_teamless_and_archives_nobody(self):
        """AC18: the migration stamps the NULL-clock teamless players and does
        NOT archive anyone, does NOT touch roster rows.

        The clockless state is staged with raw SQL -- the ORM stamps the clock on
        create, so a teamless-NULL record can only be produced the way prod got
        there (a pre-fix team-side removal)."""
        migration = self._load_migration()

        # (1) teamless with no retention clock -- the migration's whole job.
        teamless_clockless = self._player()
        self.env.cr.execute(
            "UPDATE sports_patient SET date_left_last_team = NULL WHERE id = %s",
            (teamless_clockless.id,),
        )

        # (2) an active teamless player who ALREADY has a clock -- must stay
        #     active and keep their existing clock, NOT be archived.
        active_teamless = self._player()
        self.assertTrue(active_teamless.active)
        self.assertEqual(active_teamless.date_left_last_team, self._today())

        # (3) a healthy, rostered player must be left completely alone.
        untouched = self._player(teams=self.team)

        self.env.invalidate_all()

        mail_before = self.env['mail.mail'].sudo().search_count([])
        message_before = self.env['mail.message'].sudo().search_count([])

        migration.migrate(self.env.cr, '19.0.1.6.0')
        self.env.invalidate_all()

        # AC20: raw SQL, must stay silent.
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mail_before,
                         "The migration must not queue mail")
        self.assertEqual(self.env['mail.message'].sudo().search_count([]), message_before,
                         "The migration must not post chatter")

        # (1) stamped, still active -- NO archiving.
        self.assertEqual(teamless_clockless.date_left_last_team, self._today())
        self.assertTrue(teamless_clockless.active,
                        "The migration must not archive teamless players")

        # (2) untouched -- active, existing clock.
        self.assertTrue(active_teamless.active)
        self.assertEqual(active_teamless.date_left_last_team, self._today())

        # (3) rostered player untouched.
        self.assertTrue(untouched.active)
        self.assertFalse(untouched.date_left_last_team)
        self.assertEqual(self._rel_rows(untouched), [self.team.id])

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def test_dead_archiving_cron_is_gone(self):
        """AC19: the method and its never-registered cron record are both gone."""
        self.assertFalse(
            hasattr(self.env['sports.patient'], '_cron_archive_players_without_teams'),
            "The dead cron method must not survive",
        )
        self.assertFalse(
            self.env.ref(
                'bemade_sports_clinic.ir_cron_archive_players_without_teams',
                raise_if_not_found=False,
            ),
            "The commented-out cron record must not exist",
        )
