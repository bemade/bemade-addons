"""The team form's 'Remove Players' wizard, and the recordset remove_from_team.

The wizard exists because Odoo 19 cannot put selection checkboxes on an embedded
x2many list (ListRenderer hard-defaults allowSelectors to False, and a <header>
button could not read a client-side selection anyway). It is a thin layer: the
permission model and the Law 25 retention clock live in remove_from_team and
_sync_date_left_last_team, covered here and in test_law25_roster_invariants.

Fixtures are synthetic throughout: invented names, no real player data.
"""

from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger

TP_GROUP = 'bemade_sports_clinic.group_sports_clinic_treatment_professional'


@tagged('post_install', '-at_install')
class TestTeamPlayerRemovalWizard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env['res.partner'].create({
            'name': 'Wizard Org', 'is_company': True,
        })
        cls.team = cls.env['sports.team'].create({
            'name': 'Wizard Team', 'parent_id': cls.org.id,
        })
        cls.spare_team = cls.env['sports.team'].create({
            'name': 'Wizard Spare Team', 'parent_id': cls.org.id,
        })
        cls.group_user = cls.env.ref('base.group_user')
        cls.tp_group = cls.env.ref(TP_GROUP)

        cls.admin_user = cls.env.ref('base.user_admin')

        # A treatment professional who is NOT staffed on cls.team.
        cls.outsider_tp = cls.env['res.users'].create({
            'name': 'Outsider TP', 'login': 'wiz_outsider_tp',
            'email': 'wiz_outsider_tp@example.com',
            'group_ids': [Command.link(cls.group_user.id), Command.link(cls.tp_group.id)],
        })
        # A treatment professional who IS a therapist on cls.team.
        cls.team_therapist = cls.env['res.users'].create({
            'name': 'Team Therapist', 'login': 'wiz_team_tp',
            'email': 'wiz_team_tp@example.com',
            'group_ids': [Command.link(cls.group_user.id), Command.link(cls.tp_group.id)],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.team_therapist.partner_id.id,
            'role': 'therapist',
        })

    def _player(self, last_name, teams=None):
        return self.env['sports.patient'].create({
            'first_name': 'Wizard',
            'last_name': last_name,
            'team_ids': [Command.set((teams or self.team).ids)],
        })

    def _wizard(self, team=None, user=None):
        env = self.env(user=user) if user else self.env
        return env['sports.team.player.removal.wizard'].with_context(
            active_id=(team or self.team).id,
            active_model='sports.team',
        ).create({})

    # ------------------------------------------------------------------
    # AC1 -- the button and the wizard's lines
    # ------------------------------------------------------------------

    def test_ac1_header_button_opens_wizard_on_team_form(self):
        action = self.env.ref('bemade_sports_clinic.action_team_player_removal')
        self.assertEqual(action.res_model, 'sports.team.player.removal.wizard')
        self.assertEqual(action.target, 'new')

        arch = self.env.ref('bemade_sports_clinic.sports_team_view_form').arch
        self.assertIn('Remove Players', arch,
                      "The team form needs a Remove Players header button")
        self.assertIn(str(action.id), arch,
                      "The header button must point at the wizard action")

    def test_ac1_one_line_per_current_roster_member(self):
        alpha = self._player('Alpha')
        bravo = self._player('Bravo')
        elsewhere = self._player('Elsewhere', teams=self.spare_team)

        wizard = self._wizard()

        self.assertEqual(wizard.team_id, self.team)
        self.assertEqual(wizard.line_ids.patient_id, alpha | bravo)
        self.assertNotIn(elsewhere, wizard.line_ids.patient_id)
        self.assertFalse(any(wizard.line_ids.mapped('selected')),
                         "Lines start unticked")

    def test_ac1_wizard_requires_a_team(self):
        with self.assertRaises(UserError):
            self.env['sports.team.player.removal.wizard'].create({})

    # ------------------------------------------------------------------
    # AC2 -- check-all
    # ------------------------------------------------------------------

    def test_ac2_select_all_ticks_and_unticks_every_line(self):
        self._player('Alpha')
        self._player('Bravo')

        # Drive it through a Form so the onchange really fires against the real
        # view, as it would in the UI -- this is the true check-all the existing
        # mass-assign wizard never had (its bulk_role sets a value, not a
        # selection).
        form = Form(self._wizard())

        form.select_all = True
        for index in range(len(form.line_ids)):
            with form.line_ids.edit(index) as line:
                self.assertTrue(line.selected, "Check-all must tick every line")

        form.select_all = False
        for index in range(len(form.line_ids)):
            with form.line_ids.edit(index) as line:
                self.assertFalse(line.selected,
                                 "Unticking check-all must clear every line")

    # ------------------------------------------------------------------
    # AC3 -- apply removes only the ticked players
    # ------------------------------------------------------------------

    def test_ac3_removes_only_ticked_players(self):
        alpha = self._player('Alpha')
        bravo = self._player('Bravo')
        charlie = self._player('Charlie')

        wizard = self._wizard()
        wizard.line_ids.filtered(
            lambda line: line.patient_id in (alpha | charlie)
        ).selected = True

        action = wizard.action_remove()

        # The wizard closes after a successful removal: the returned action
        # chains a window-close so the dialog does not stay open (the client
        # dialog-close itself is UAT-verified, but the returned shape is not).
        self.assertEqual(
            (action.get("params") or {}).get("next"),
            {"type": "ir.actions.act_window_close"},
            "action_remove must chain act_window_close so the wizard dialog closes",
        )

        self.assertNotIn(alpha, self.team.patient_ids)
        self.assertNotIn(charlie, self.team.patient_ids)
        self.assertIn(bravo, self.team.patient_ids, "Unticked players stay")
        self.assertTrue(bravo.active)
        # They were on their last team, so their retention clock is stamped, but
        # removal never archives them (auto-archive dropped 2026-07-16).
        self.assertTrue(alpha.active)
        self.assertTrue(charlie.active)
        self.assertEqual(alpha.date_left_last_team, fields.Date.context_today(alpha))
        self.assertEqual(charlie.date_left_last_team, fields.Date.context_today(charlie))

    def test_ac3_nothing_ticked_raises(self):
        self._player('Alpha')
        wizard = self._wizard()

        with self.assertRaises(UserError):
            wizard.action_remove()

    def test_ac3_select_all_then_apply_clears_the_roster(self):
        self._player('Alpha')
        self._player('Bravo')
        wizard = self._wizard()
        wizard.select_all = True
        wizard._onchange_select_all()

        wizard.action_remove()

        self.assertFalse(self.team.patient_ids)

    # ------------------------------------------------------------------
    # AC4 -- permissions (enforced in remove_from_team, not the view)
    # ------------------------------------------------------------------

    def test_ac4_admin_succeeds(self):
        alpha = self._player('Alpha')
        wizard = self._wizard(user=self.admin_user)
        wizard.line_ids.selected = True

        wizard.action_remove()

        self.assertNotIn(alpha, self.team.patient_ids)

    @mute_logger('odoo.addons.bemade_sports_clinic.models.patient')
    def test_ac4_treatment_professional_not_on_team_gets_access_error(self):
        # Asserted against remove_from_team, where the real per-team check lives
        # (the view's groups= only hides the button). Building the wizard as the
        # outsider would trip the patient record rules first and prove nothing
        # about the permission model.
        alpha = self._player('Alpha')

        with self.assertRaises(AccessError):
            alpha.with_user(self.outsider_tp).remove_from_team(self.team.id)
        self.assertIn(alpha, self.team.patient_ids)
        self.assertTrue(alpha.active)

    def test_ac4_therapist_on_team_succeeds(self):
        alpha = self._player('Alpha')

        alpha.with_user(self.team_therapist).remove_from_team(self.team.id)

        self.assertNotIn(alpha, self.team.patient_ids)

    # ------------------------------------------------------------------
    # AC5 -- the recordset remove_from_team
    # ------------------------------------------------------------------

    def test_ac5_bulk_call_posts_one_team_message_not_per_player(self):
        """Dev-review round 2: a bulk removal posts ONE summary on the TEAM
        chatter and NOTHING on the individual players, so the annual
        'clear all teams' run does not flood every player's chatter.
        A single-record call is unchanged (see the single-record test below)."""
        alpha = self._player('Alpha')
        bravo = self._player('Bravo')
        players = alpha | bravo

        # Baseline chatter counts BEFORE the removal.
        player_before = {p.id: len(p.message_ids) for p in players}
        team_before = len(self.team.message_ids)

        result = players.with_user(self.admin_user).remove_from_team(self.team.id)

        self.assertFalse(self.team.patient_ids)

        # Exactly ONE new message on the team.
        self.assertEqual(
            len(self.team.message_ids) - team_before, 1,
            "The bulk clear posts exactly one summary on the team chatter",
        )
        # ZERO new messages on any removed player.
        for player in players:
            self.assertEqual(
                len(player.message_ids), player_before[player.id],
                "The bulk path posts nothing on individual player chatters",
            )

        # The single team summary names every removed player.
        summary = self.env['mail.message'].search([
            ('model', '=', 'sports.team'),
            ('res_id', '=', self.team.id),
            ('body', 'ilike', 'removed from team'),
        ])
        self.assertEqual(len(summary), 1, "One summary message on the team")
        self.assertIn('Alpha', summary.body)
        self.assertIn('Bravo', summary.body)
        self.assertIn('2 players', result['params']['message'])

    def test_ac5_bulk_summary_lists_removed_players_and_never_archives(self):
        """Dev-review round 3: the team summary lists the players removed and
        makes NO claim about archiving -- removal no longer archives anyone.
        Both players stay active; the one left teamless just gets a clock."""
        alpha = self._player('Alpha')  # only on cls.team -> left teamless
        bravo = self._player('Bravo', teams=self.team | self.spare_team)  # keeps spare
        players = alpha | bravo

        players.with_user(self.admin_user).remove_from_team(self.team.id)

        summary = self.env['mail.message'].search([
            ('model', '=', 'sports.team'),
            ('res_id', '=', self.team.id),
            ('body', 'ilike', 'removed from team'),
        ])
        self.assertEqual(len(summary), 1)
        self.assertIn('Alpha', summary.body)
        self.assertIn('Bravo', summary.body)
        self.assertNotIn('archived', summary.body.lower(),
                         "The summary must not mention archiving -- nobody is archived")
        # Neither player is archived; the teamless one carries a retention clock.
        self.assertTrue(alpha.active, "Alpha is not archived, only teamless")
        self.assertTrue(bravo.active, "Bravo still has the spare team")
        self.assertEqual(alpha.date_left_last_team, fields.Date.context_today(alpha))
        self.assertFalse(bravo.date_left_last_team)

    def test_ac5_permission_check_runs_once_not_per_player(self):
        # Task 1260 extracted the removal policy into the single predicate
        # sports.patient._may_remove_from_team(team). The #1257 property this
        # test guards -- "the permission check is per TEAM, not per player" --
        # now means: that predicate is evaluated exactly ONCE per call, however
        # many players the recordset holds. (The previous version counted
        # has_group calls by frame introspection, which is unreliable across
        # Odoo builds; counting the predicate directly is robust and tests the
        # same guarantee against the new structure.)
        players = self._player('Alpha') | self._player('Bravo') | self._player('Charlie')
        Patient = type(self.env['sports.patient'])
        real_may = Patient._may_remove_from_team
        calls = []

        def counting_may(records, team):
            calls.append(team.id)
            return real_may(records, team)

        with patch.object(Patient, '_may_remove_from_team', counting_may):
            players.with_user(self.admin_user).remove_from_team(self.team.id)

        self.assertEqual(
            calls, [self.team.id],
            "The permission check is per-team, not per-player: the removal "
            "predicate is evaluated once for the whole call, however many "
            "players it removes",
        )

    def test_ac5_roster_write_is_batched(self):
        players = self._player('Alpha') | self._player('Bravo') | self._player('Charlie')
        roster_writes = []
        Patient = type(self.env['sports.patient'])
        real_write = Patient.write

        def counting_write(records, vals):
            if 'team_ids' in vals:
                roster_writes.append(len(records))
            return real_write(records, vals)

        with patch.object(Patient, 'write', counting_write):
            players.with_user(self.admin_user).remove_from_team(self.team.id)

        self.assertEqual(
            roster_writes, [3],
            "One batched roster write for all three players, so "
            "recompute_followers and _sync_date_left_last_team each run once",
        )

    def test_ac5_single_record_call_sites_keep_their_message(self):
        alpha = self._player('Alpha', teams=self.team | self.spare_team)

        result = alpha.with_user(self.admin_user).remove_from_team(self.team.id)

        self.assertEqual(
            result['params']['message'],
            'Player successfully removed from team.',
            "The single-record return message is depended on by existing callers",
        )
        self.assertEqual(result['params']['type'], 'success')

    def test_ac5_empty_recordset_is_a_no_op(self):
        empty = self.env['sports.patient']
        result = empty.with_user(self.admin_user).remove_from_team(self.team.id)
        self.assertEqual(result['type'], 'ir.actions.client')
