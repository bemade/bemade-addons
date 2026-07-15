"""Roster invariants for the Law 25 retention clock and player archiving.

Three invariants must hold on EVERY path that changes a player's roster, not
just the patient-side write they were originally hooked on:

I1  teamless <=> date_left_last_team set. The Law 25 retention rule keys on this
    date. A NULL clock never surfaces for anonymization (the record is kept
    forever); a stale clock ages the record out years early. Both are compliance
    failures, in opposite directions.
I2  teamless => archived. Enforced when a player LOSES their last team.
I3  archived => not rostered.

Every test here drives a REAL removal path -- team.write, team.create,
team.unlink, patient.write, remove_from_team. None of them call an enforcement
helper directly: the bug these cover survived for years precisely because the
tests called the archiving cron by hand while the cron itself never ran.

Fixtures are synthetic throughout: invented names, no real player data.
"""

import importlib.util
import os
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


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
    # I2 -- teamless => archived
    # ------------------------------------------------------------------

    def test_i2_remove_from_last_team_archives(self):
        """AC8: via a real removal, never by calling an archiving helper."""
        player = self._player(teams=self.team)
        self.assertTrue(player.active)

        player.remove_from_team(self.team.id)

        self.assertFalse(player.active)
        self.assertEqual(player.date_left_last_team, self._today())

    def test_i2_remove_with_another_team_does_not_archive(self):
        """AC9: still on another team => still active, clock still NULL."""
        player = self._player(teams=self.team | self.other_team)

        player.remove_from_team(self.team.id)

        self.assertTrue(player.active, "A player with another team stays active")
        self.assertFalse(player.date_left_last_team)
        self.assertEqual(player.team_ids, self.other_team)

    def test_i2_team_side_unlink_archives(self):
        """AC10: the per-row 'x' on the team form's Players tab."""
        player = self._player(teams=self.team)
        self.assertTrue(player.active)

        self.team.write({'patient_ids': [Command.unlink(player.id)]})

        self.assertFalse(player.active)

    def test_i2_direct_patient_write_archives(self):
        """AC11: patient.write({'team_ids': [Command.clear()]})."""
        player = self._player(teams=self.team)
        self.assertTrue(player.active)

        player.write({'team_ids': [Command.clear()]})

        self.assertFalse(player.active)

    def test_i2_team_unlink_archives(self):
        """AC12: deleting a team archives the players it leaves teamless."""
        team = self.env['sports.team'].create({
            'name': 'Invariants Team E', 'parent_id': self.org.id,
        })
        stays = self._player(teams=team | self.other_team)
        goes = self._player(teams=team)
        self.assertTrue(goes.active)

        team.unlink()

        self.assertFalse(goes.active, "Teamless after the delete => archived")
        self.assertTrue(stays.active, "Still on another team => untouched")

    def test_i2_create_teamless_does_not_archive(self):
        """A player who never joined a team has not LEFT one.

        Deviation from the plan, deliberate: enforcing I2 in create would archive
        every player created before their team is assigned, making
        'create the player, roster them afterwards' produce an
        archived-and-rostered record -- the very I3 state the team-side guard
        rejects. The retention clock still starts, which is what Law 25 keys on.
        """
        player = self._player()

        self.assertTrue(player.active, "Creation must not archive")
        self.assertEqual(player.date_left_last_team, self._today(),
                         "...but the retention clock still starts")

    # ------------------------------------------------------------------
    # I3 -- archived => not rostered
    # ------------------------------------------------------------------

    def test_i3_archiving_clears_roster(self):
        """AC13: archiving a rostered player clears team_ids and stamps the clock.

        Asserted against the rel table with active_test=False -- reading
        team.patient_ids under the default context would hide the player and pass
        vacuously.
        """
        player = self._player(teams=self.team | self.other_team)
        self.assertTrue(self._rel_rows(player))

        player.write({'active': False})

        self.assertFalse(player.team_ids)
        self.assertEqual(player.date_left_last_team, self._today())
        self.assertFalse(
            self._rel_rows(player),
            "No rel row may survive: archived => not rostered",
        )
        self.assertNotIn(
            player,
            self.team.with_context(active_test=False).patient_ids,
            "The team must not still roster the archived player",
        )

    def test_i3_unarchiving_does_not_restore_teams(self):
        """AC13: we cannot know which teams they were on; they come back teamless."""
        player = self._player(teams=self.team)
        player.write({'active': False})

        player.write({'active': True})

        self.assertTrue(player.active)
        self.assertFalse(player.team_ids, "Unarchiving must not restore teams")
        self.assertEqual(player.date_left_last_team, self._today())

    def test_i3_toggle_active_clears_roster(self):
        """toggle_active/action_archive both funnel through write."""
        player = self._player(teams=self.team)

        player.action_archive()

        self.assertFalse(player.active)
        self.assertFalse(self._rel_rows(player))

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_team')
    def test_i3_team_write_link_archived_player_raises(self):
        """AC14: the team-side guard FIRES.

        The player is archived while teamless, so nothing else could have removed
        them; if the guard were reading patient_ids naively (under active_test)
        it would see an empty roster, raise nothing, and this test would fail --
        which is the point. Proving the raise proves the guard is not blind.
        """
        archived = self._player()
        archived.write({'active': False})
        self.assertFalse(archived.active)

        with self.assertRaises(ValidationError) as ctx:
            self.team.write({'patient_ids': [Command.link(archived.id)]})
        self.assertIn('archived', str(ctx.exception).lower())

    @mute_logger('odoo.addons.bemade_sports_clinic.models.sports_team')
    def test_i3_team_create_with_archived_player_raises(self):
        """AC14: same guard on team.create."""
        archived = self._player()
        archived.write({'active': False})

        with self.assertRaises(ValidationError):
            self.env['sports.team'].create({
                'name': 'Invariants Team F',
                'parent_id': self.org.id,
                'patient_ids': [Command.set(archived.ids)],
            })

    def test_i3_team_write_link_active_player_succeeds(self):
        """AC14: the guard is selective, not a blanket refusal."""
        active_player = self._player()
        self.assertTrue(active_player.active)

        self.team.write({'patient_ids': [Command.link(active_player.id)]})

        self.assertIn(active_player, self.team.patient_ids)
        self.assertFalse(active_player.date_left_last_team)

    # ------------------------------------------------------------------
    # Recursion -- I2 and I3 trigger each other
    # ------------------------------------------------------------------

    def _counting_write(self, limit=25):
        """Patch sports.patient.write to fail loudly instead of hanging.

        Runaway mutual recursion would otherwise blow the Python stack (or spin a
        worker); cap the re-entrancy so the failure is a readable assertion.
        """
        Patient = type(self.env['sports.patient'])
        original = Patient.write
        calls = []

        def counting_write(records, vals):
            calls.append(dict(vals))
            if len(calls) > limit:
                raise AssertionError(
                    "runaway recursion in sports.patient.write: %s" % (calls,)
                )
            return original(records, vals)

        return patch.object(Patient, 'write', counting_write), calls

    def test_recursion_direction_a_archive_rostered_player_terminates(self):
        """AC15: archive a rostered player -> I3 clears teams -> I2 sees the
        player is already inactive and stops."""
        player = self._player(teams=self.team | self.other_team)
        patcher, calls = self._counting_write()

        with patcher:
            player.write({'active': False})

        self.assertFalse(player.active)
        self.assertFalse(player.team_ids)
        self.assertEqual(player.date_left_last_team, self._today())
        self.assertLessEqual(len(calls), 25, "write must not bounce indefinitely")

    def test_recursion_direction_b_remove_last_team_terminates(self):
        """AC16: remove the last team -> I2 archives -> I3 sees an empty roster
        and stops."""
        player = self._player(teams=self.team)
        patcher, calls = self._counting_write()

        with patcher:
            player.write({'team_ids': [Command.clear()]})

        self.assertFalse(player.active)
        self.assertFalse(player.team_ids)
        self.assertEqual(player.date_left_last_team, self._today())
        self.assertLessEqual(len(calls), 25)

    def test_recursion_already_archived_player_does_not_retrigger(self):
        """AC17: writing to an already-archived, teamless player is inert."""
        player = self._player(teams=self.team)
        player.write({'active': False})
        clock = player.date_left_last_team
        patcher, calls = self._counting_write()

        with patcher:
            player.write({'team_info_notes': 'Synthetic note'})
            player.write({'active': False})

        self.assertFalse(player.active)
        self.assertFalse(player.team_ids)
        self.assertEqual(player.date_left_last_team, clock,
                         "The clock must not be re-stamped")
        self.assertLessEqual(len(calls), 25)

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

    def test_migration_heals_all_three_broken_states(self):
        """AC18: the three strays the old code could leave behind.

        The broken states are built with raw SQL on purpose -- the ORM now
        refuses to create them, which is the whole point of the fix, so they can
        only be staged the way prod actually got there.
        """
        migration = self._load_migration()

        # (1) archived but still rostered (I3) - stage the rel row behind the ORM
        archived_rostered = self._player(teams=self.team)
        self.env.cr.execute(
            "UPDATE sports_patient SET active = false, date_left_last_team = NULL"
            " WHERE id = %s", (archived_rostered.id,),
        )

        # (2) teamless with no retention clock (I1)
        teamless_clockless = self._player()
        self.env.cr.execute(
            "UPDATE sports_patient SET date_left_last_team = NULL WHERE id = %s",
            (teamless_clockless.id,),
        )

        # (3) active and teamless (I2) - the players the dead cron never swept
        active_teamless = self._player()

        # A healthy, rostered player must be left completely alone.
        untouched = self._player(teams=self.team)

        self.env.invalidate_all()

        mail_before = self.env['mail.mail'].sudo().search_count([])
        message_before = self.env['mail.message'].sudo().search_count([])

        migration.migrate(self.env.cr, '19.0.1.6.0')
        self.env.invalidate_all()

        # AC20: the migration is raw SQL and must stay silent -- it must not
        # notify anyone about players archived years after the fact.
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mail_before,
                         "The migration must not queue mail")
        self.assertEqual(self.env['mail.message'].sudo().search_count([]), message_before,
                         "The migration must not post chatter")

        # (1) rel rows dropped, then stamped, then left archived
        self.assertFalse(self._rel_rows(archived_rostered))
        self.assertFalse(archived_rostered.active)
        self.assertEqual(archived_rostered.date_left_last_team, self._today(),
                         "Step (a) must run before (b), else the clock stays NULL")

        # (2) stamped
        self.assertEqual(teamless_clockless.date_left_last_team, self._today())
        self.assertFalse(teamless_clockless.active)

        # (3) archived
        self.assertFalse(active_teamless.active)
        self.assertEqual(active_teamless.date_left_last_team, self._today())

        # rostered player untouched
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
