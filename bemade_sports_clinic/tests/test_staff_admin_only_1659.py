"""Task 1659 — only administrators change staff lines. Synthetic fixtures.

Owner decision (2026-10-24): for internal users who are not clinic
administrators or system administrators, creating, writing or deleting staff
lines is refused. Reading stays as today. The app's own flows run sudo with
their own checks.

Acceptance criteria covered here:

* AC-1 An internal non-admin therapist (``itp``) cannot create, write or
  unlink ``sports.team.staff``, ``sports.staff.grant``,
  ``sports.organization.staff`` (nor its per-team overrides) — AccessError;
  reading still works.
* AC-2 A clinic administrator can, and so can a system administrator.
* AC-3 The adversarial-review scenario is refused: the internal therapist
  cannot add themselves as organization staff to reach an organization's
  players; nor re-parent a team under an organization they staff.
* AC-4 The therapist auto-sync still works (a staff line with a therapist
  role gives the user the therapist group).
* AC-5 App flows that create staff lines under sudo still work for the
  internal therapist: an event they create with an assigned therapist opens
  that therapist's event coverage on the team.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common


@tagged('post_install', '-at_install')
class TestStaffAdminOnly1659(Parity1577Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.org_other = env['res.partner'].create({'name': 'G1659 Other Org', 'is_company': True})
        cls.team_other = env['sports.team'].create({'name': 'G1659 Team', 'parent_id': cls.org_other.id})
        cls.team_plain = env['sports.team'].create({'name': 'G1659 Plain Team'})
        cls.secret_player = env['sports.patient'].create({
            'first_name': 'Secret', 'last_name': 'Synthetic',
            'team_ids': [Command.set([cls.team_other.id])]})
        cls.sysadmin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'G1659 Sysadmin', 'login': 'g1659.sys@example.com',
            # A system administrator who is a clinic « Internal User », not a
            # clinic administrator.
            'group_ids': [Command.set([env.ref('base.group_user').id, env.ref('base.group_system').id,
                                       env.ref('bemade_sports_clinic.group_sports_clinic_user').id])]})
        cls.newcomer = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'G1659 Newcomer', 'login': 'g1659.new@example.com',
            'group_ids': [Command.set([env.ref('base.group_user').id])]})
        cls.own_row = env['sports.team.staff'].search([
            ('team_id', '=', cls.team_a.id), ('partner_id', '=', cls.itp.partner_id.id)])
        cls.org_line = env['sports.organization.staff'].create({
            'organization_id': cls.org_other.id, 'partner_id': cls.newcomer.partner_id.id,
            'role': 'coach'})
        now = fields.Datetime.now()
        cls.grant = env['sports.staff.grant'].create({
            'scope': 'team', 'team_id': cls.team_a.id, 'partner_id': cls.newcomer.partner_id.id,
            'role': 'therapist', 'date_start': now + timedelta(days=5), 'date_end': now + timedelta(days=6)})

    def _refused(self, func):
        with self.assertRaises(AccessError), mute_logger('odoo.models', 'odoo.addons.base.models.ir_model'):
            func()

    # -- AC-1 -------------------------------------------------------------
    def test_internal_therapist_cannot_change_staff_lines(self):
        env = self.env(user=self.itp)
        partner = self.itp.partner_id.id
        now = fields.Datetime.now()
        # sports.team.staff
        self._refused(lambda: env['sports.team.staff'].create({
            'team_id': self.team_other.id, 'partner_id': partner, 'role': 'therapist'}))
        self._refused(lambda: self.own_row.with_user(self.itp).write({'role': 'head_therapist'}))
        self._refused(lambda: self.own_row.with_user(self.itp).unlink())
        # sports.staff.grant
        self._refused(lambda: env['sports.staff.grant'].create({
            'scope': 'team', 'team_id': self.team_other.id, 'partner_id': partner,
            'role': 'therapist', 'date_start': now, 'date_end': now + timedelta(days=1)}))
        self._refused(lambda: self.grant.with_user(self.itp).write({'note': 'Synthetic note'}))
        self._refused(lambda: self.grant.with_user(self.itp).unlink())
        # sports.organization.staff (+ overrides)
        self._refused(lambda: env['sports.organization.staff'].create({
            'organization_id': self.org_other.id, 'partner_id': partner, 'role': 'therapist'}))
        self._refused(lambda: self.org_line.with_user(self.itp).write({'role': 'therapist'}))
        self._refused(lambda: self.org_line.with_user(self.itp).unlink())
        self._refused(lambda: env['sports.organization.staff.override'].create({
            'line_id': self.org_line.id, 'team_id': self.team_other.id, 'role': 'therapist'}))
        # Reading stays.
        self.assertTrue(self.own_row.with_user(self.itp).read(['role']))
        self.assertTrue(env['sports.organization.staff'].search_count([]))
        self.assertTrue(env['sports.staff.grant'].search_count([]))

    # -- AC-2 -------------------------------------------------------------
    def test_admins_can_change_staff_lines(self):
        for admin in (self.cadmin, self.sysadmin):
            env = self.env(user=admin)
            row = env['sports.team.staff'].create({
                'team_id': self.team_plain.id, 'partner_id': self.newcomer.partner_id.id, 'role': 'coach'})
            row.write({'role': 'head_coach'})
            row.unlink()
            line = env['sports.organization.staff'].create({
                'organization_id': self.org_other.id, 'partner_id': admin.partner_id.id, 'role': 'doctor'})
            line.write({'role': 'therapist'})
            line.unlink()
            now = fields.Datetime.now()
            grant = env['sports.staff.grant'].create({
                'scope': 'team', 'team_id': self.team_other.id, 'partner_id': self.newcomer.partner_id.id,
                'role': 'therapist', 'date_start': now + timedelta(days=3), 'date_end': now + timedelta(days=4)})
            grant.write({'note': 'Synthetic note'})
            grant.unlink()

    # -- AC-3 -------------------------------------------------------------
    def test_adversarial_org_staff_self_add_refused(self):
        Patient = self.env['sports.patient'].with_user(self.itp)
        self.assertFalse(Patient.search_count([('id', '=', self.secret_player.id)]))
        self._refused(lambda: self.env['sports.organization.staff'].with_user(self.itp).create({
            'organization_id': self.org_other.id, 'partner_id': self.itp.partner_id.id,
            'role': 'head_therapist'}))
        self.assertFalse(Patient.search_count([('id', '=', self.secret_player.id)]))

    def test_reparent_team_admin_only(self):
        self._refused(lambda: self.team_other.with_user(self.itp).write({'parent_id': self.org.id}))
        self.team_unstaffed.with_user(self.cadmin).write({'parent_id': self.org_other.id})
        self.assertEqual(self.team_unstaffed.parent_id, self.org_other)

    # -- AC-4 -------------------------------------------------------------
    def test_therapist_auto_sync_still_works(self):
        tp_group = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        self.assertNotIn(tp_group, self.newcomer.all_group_ids)
        self.env['sports.team.staff'].with_user(self.cadmin).create({
            'team_id': self.team_plain.id, 'partner_id': self.newcomer.partner_id.id, 'role': 'therapist'})
        self.newcomer.invalidate_recordset()
        self.assertIn(tp_group, self.newcomer.all_group_ids)

    # -- AC-5 -------------------------------------------------------------
    def test_event_coverage_created_for_internal_therapist(self):
        # Review fixes 2026-10-24: an event assignee is a treatment professional.
        self.newcomer.write({'group_ids': [Command.link(
            self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id)]})
        start = fields.Datetime.now() + timedelta(hours=2)
        event = self.env['sports.event'].with_user(self.itp).create({
            'name': 'G1659 Coverage', 'event_type': 'game',
            'team_ids': [Command.set([self.team_a.id])],
            'date_start': start, 'date_end': start + timedelta(hours=2),
            'assigned_staff_ids': [Command.set([self.newcomer.id])],
            'state': 'confirmed',
        })
        rows = self.env['sports.team.staff'].search([
            ('team_id', '=', self.team_a.id), ('partner_id', '=', self.newcomer.partner_id.id)])
        self.assertTrue(rows, 'event coverage row created through sudo')
        self.assertIn(event, rows.temporary_event_ids)
