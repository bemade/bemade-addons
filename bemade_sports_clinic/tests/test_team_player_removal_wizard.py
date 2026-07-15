"""The team form's 'Remove Players' wizard, and the recordset remove_from_team.

The wizard exists because Odoo 19 cannot put selection checkboxes on an embedded
x2many list (ListRenderer hard-defaults allowSelectors to False, and a <header>
button could not read a client-side selection anyway). It is a thin layer: the
permission model and the roster invariants live in remove_from_team and
_sync_teamless_state, covered here and in test_law25_roster_invariants.

Fixtures are synthetic throughout: invented names, no real player data.
"""

import sys
from unittest.mock import patch

from odoo import Command
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

        wizard.action_remove()

        self.assertNotIn(alpha, self.team.patient_ids)
        self.assertNotIn(charlie, self.team.patient_ids)
        self.assertIn(bravo, self.team.patient_ids, "Unticked players stay")
        self.assertTrue(bravo.active)
        # They were on their last team, so they are archived (AC8/I2).
        self.assertFalse(alpha.active)
        self.assertFalse(charlie.active)

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

    def test_ac5_multi_player_call_removes_all_and_posts_chatter_on_each(self):
        alpha = self._player('Alpha')
        bravo = self._player('Bravo')
        players = alpha | bravo

        result = players.with_user(self.admin_user).remove_from_team(self.team.id)

        self.assertFalse(self.team.patient_ids)
        for player in players:
            messages = self.env['mail.message'].search([
                ('model', '=', 'sports.patient'),
                ('res_id', '=', player.id),
                ('body', 'ilike', 'removed from team'),
            ])
            self.assertTrue(messages, "Each player keeps their own audit trail")
        self.assertIn('2 players', result['params']['message'])

    def test_ac5_permission_check_runs_once_not_per_player(self):
        players = self._player('Alpha') | self._player('Bravo') | self._player('Charlie')
        calls = []
        Users = type(self.env['res.users'])
        real_has_group = Users.has_group

        def counting_has_group(user, group_ext_id):
            # Count ONLY the checks made directly by remove_from_team's own body.
            # Record rules and group-restricted fields call has_group plenty of
            # times on their own; counting those would measure the ORM, not this
            # method. The old loop of single-record calls would land here once
            # per player.
            if sys._getframe(1).f_code.co_name == 'remove_from_team':
                calls.append(group_ext_id)
            return real_has_group(user, group_ext_id)

        with patch.object(Users, 'has_group', counting_has_group):
            players.with_user(self.admin_user).remove_from_team(self.team.id)

        self.assertEqual(
            calls, ['base.group_system', TP_GROUP],
            "The permission check is per-team, not per-player: each group is "
            "checked once for the whole call, however many players it removes",
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
            "recompute_followers and _sync_teamless_state each run once",
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
