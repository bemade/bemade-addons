"""
Coverage for team.role.mass.assign.wizard and team.role.mass.assign.line.

Acceptance criteria:
- default_get raises UserError when called without a default_user_id context key.
- default_get builds one line per sports.team; the team_a line is pre-selected with
  role='coach' (matching the fixture staff row); the team_b line is unselected.
- _onchange_bulk_role propagates the chosen role to every selected line.
- _onchange_selected on a line that was just toggled on inherits the wizard bulk_role.
- action_apply upserts sports.team.staff correctly and returns act_window_close.
- action_apply raises UserError when a selected line has no role and bulk_role is unset.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import mute_logger  # noqa: F401  (available for future use)


@tagged('post_install', '-at_install')
class TestCovTeamRoleMassAssign(TransactionCase):
    """Coverage for team.role.mass.assign.wizard (default_get, onchanges, action_apply)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.org = cls.env['res.partner'].create({'name': 'MA Org', 'is_company': True})
        cls.team_a = cls.env['sports.team'].create({
            'name': 'MA Team A',
            'parent_id': cls.org.id,
        })
        cls.team_b = cls.env['sports.team'].create({
            'name': 'MA Team B',
            'parent_id': cls.org.id,
        })

        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'MA User',
            'login': 'ma.user@example.com',
            'group_ids': [Command.link(cls.env.ref('base.group_user').id)],
        })

        # Pre-existing staff row: user is already a coach on team_a.
        cls.env['sports.team.staff'].create({
            'team_id': cls.team_a.id,
            'partner_id': cls.user.partner_id.id,
            'role': 'coach',
        })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wizard_form(self, user=None, **ctx):
        """Return an open Form for the wizard, pre-loaded with default_user_id."""
        user = user or self.user
        return Form(
            self.env['team.role.mass.assign.wizard'].with_context(
                default_user_id=user.id, **ctx
            )
        )

    def _find_line_for_team(self, wizard, team):
        """Return the wizard line record for the given team, or None."""
        return wizard.line_ids.filtered(lambda l: l.team_id == team)

    # ------------------------------------------------------------------
    # 1. default_get raises when no user in context
    # ------------------------------------------------------------------

    def test_default_get_requires_user(self):
        """default_get without default_user_id context must raise UserError."""
        with self.assertRaises(UserError):
            self.env['team.role.mass.assign.wizard'].default_get(['user_id', 'line_ids'])

    # ------------------------------------------------------------------
    # 2. default_get builds correct lines
    # ------------------------------------------------------------------

    def test_default_get_builds_lines_from_teams(self):
        """Lines for team_a and team_b are built correctly by default_get."""
        form = self._wizard_form()
        wizard = form.save()

        line_a = self._find_line_for_team(wizard, self.team_a)
        line_b = self._find_line_for_team(wizard, self.team_b)

        self.assertTrue(line_a, "Expected a line for team_a")
        self.assertTrue(line_b, "Expected a line for team_b")

        self.assertTrue(line_a.selected, "team_a line should be pre-selected (user is staff)")
        self.assertEqual(line_a.role, 'coach', "team_a line role should reflect existing staff role")

        self.assertFalse(line_b.selected, "team_b line should not be selected (user not staff)")

    # ------------------------------------------------------------------
    # 3. _onchange_bulk_role propagates to selected lines
    # ------------------------------------------------------------------

    def test_onchange_bulk_role_sets_selected_lines(self):
        """Setting bulk_role propagates 'therapist' to every selected line."""
        form = self._wizard_form()
        form.bulk_role = 'therapist'
        wizard = form.save()

        for line in wizard.line_ids:
            if line.selected:
                self.assertEqual(
                    line.role,
                    'therapist',
                    f"Selected line for {line.team_id.name} should have role 'therapist'",
                )

    # ------------------------------------------------------------------
    # 4. _onchange_selected inherits bulk_role
    # ------------------------------------------------------------------

    def test_onchange_selected_uses_bulk_role(self):
        """Toggling a line to selected inherits the wizard's bulk_role."""
        form = self._wizard_form()
        form.bulk_role = 'doctor'

        # Find the index of the team_b line within the Form's line_ids.
        # We must locate it by iterating; Form line_ids are ordered by team name.
        wizard_preview = form.save()
        team_b_index = None
        for i, line in enumerate(wizard_preview.line_ids):
            if line.team_id == self.team_b:
                team_b_index = i
                break
        self.assertIsNotNone(team_b_index, "team_b line must exist in wizard lines")

        # Re-open a fresh form to manipulate via Form API (onchanges fire properly).
        form2 = self._wizard_form()
        form2.bulk_role = 'doctor'
        with form2.line_ids.edit(team_b_index) as line:
            line.selected = True
        wizard2 = form2.save()

        line_b = self._find_line_for_team(wizard2, self.team_b)
        self.assertTrue(line_b.selected, "team_b line should be selected")
        self.assertEqual(line_b.role, 'doctor', "team_b line should inherit bulk_role 'doctor'")

    # ------------------------------------------------------------------
    # 5. action_apply upserts staff and returns act_window_close
    # ------------------------------------------------------------------

    def test_action_apply_upserts_staff(self):
        """action_apply creates a new staff row for team_b and returns act_window_close."""
        form = self._wizard_form()
        wizard = form.save()

        # Find the team_b line and set it up for assignment.
        line_b = self._find_line_for_team(wizard, self.team_b)
        self.assertTrue(line_b, "team_b line must exist")
        line_b.write({'selected': True, 'role': 'therapist'})

        result = wizard.action_apply()

        self.assertEqual(result.get('type'), 'ir.actions.act_window_close')

        staff_b = self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_b.id),
            ('partner_id', '=', self.user.partner_id.id),
        ], limit=1)
        self.assertTrue(staff_b, "A staff row for (team_b, user) should now exist")
        self.assertEqual(staff_b.role, 'therapist', "Staff role should be 'therapist'")

    def test_action_apply_updates_existing_staff_role(self):
        """action_apply updates an existing staff role when the line is selected."""
        form = self._wizard_form()
        wizard = form.save()

        # team_a already has a staff row with role='coach'; change it to 'head_coach'.
        line_a = self._find_line_for_team(wizard, self.team_a)
        self.assertTrue(line_a, "team_a line must exist")
        line_a.write({'selected': True, 'role': 'head_coach'})

        wizard.action_apply()

        staff_a = self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_a.id),
            ('partner_id', '=', self.user.partner_id.id),
        ], limit=1)
        self.assertEqual(staff_a.role, 'head_coach', "Existing staff role should be updated to 'head_coach'")

    def test_action_apply_leaves_unselected_lines_untouched(self):
        """action_apply must not remove or alter staff for unselected lines."""
        form = self._wizard_form()
        wizard = form.save()

        # Ensure team_a line is unselected; team_a staff row must survive.
        line_a = self._find_line_for_team(wizard, self.team_a)
        line_a.write({'selected': False})

        wizard.action_apply()

        staff_a = self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_a.id),
            ('partner_id', '=', self.user.partner_id.id),
        ])
        self.assertTrue(staff_a, "Existing staff row for team_a must survive when line is unselected")

    # ------------------------------------------------------------------
    # 6. action_apply raises UserError with selected line, no role, no bulk
    # ------------------------------------------------------------------

    def test_action_apply_requires_role(self):
        """action_apply raises UserError when a selected line has no role and no bulk_role."""
        form = self._wizard_form()
        wizard = form.save()

        # Select team_b but give it no role; leave bulk_role unset.
        line_b = self._find_line_for_team(wizard, self.team_b)
        self.assertTrue(line_b, "team_b line must exist")
        line_b.write({'selected': True, 'role': False})

        # Ensure bulk_role is also unset on the wizard.
        wizard.write({'bulk_role': False})

        with self.assertRaises(UserError):
            wizard.action_apply()
