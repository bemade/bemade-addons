"""Triage/regression for the 'disappearing data' pattern: portal templates that
read res.users-linked fields on records referencing users the portal viewer
cannot read (cross-team). Each renders a view as a portal TP (staffs team_a)
referencing a user who only staffs team_b.
"""
from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovPortalCrossTeam(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A therapist who staffs ONLY team_b -> pc.tp (team_a) cannot read this user.
        cls.other = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Cross Team Therapist', 'login': 'pc.crossteam@example.com', 'password': 'x',
            'group_ids': [Command.set([
                cls.env.ref('base.group_portal').id,
                cls.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        cls.env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.other.partner_id.id, 'role': 'therapist',
        })

    def test_event_detail_timesheet_table_other_therapist(self):
        # A timesheet on the event filed by another therapist: the page must
        # not 500 — and since the confidentiality fix (dev-review 2026-07-04)
        # the other therapist's row must NOT render: TPs only see their own
        # timesheets on the event detail.
        self.env['sports.event.timesheet'].create({
            'event_id': self.event.id, 'user_id': self.other.id,
        })
        self.env.flush_all()
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}')
        self.assertEqual(resp.status_code, 200, "detail must not 500 on a cross-user timesheet")
        self.assertNotIn('<span>Cross Team Therapist</span>', resp.text,
                         "other therapists' timesheet rows must not render")

    def test_injury_edit_prechecks_cross_team_tp(self):
        self.injury.sudo().write({'treatment_professional_ids': [Command.set([self.other.id])]})
        self.env.flush_all()
        self._login_tp()
        resp = self.url_open(f'/my/injury/edit?injury_id={self.injury.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertRegex(resp.text, r'value="%s"[^>]*checked' % self.other.id,
                         "the assigned (cross-team) TP checkbox should be pre-checked")

    def test_treatment_notes_other_author(self):
        # A note authored by a therapist the viewer can't read: the notes view
        # renders note.user_id.name.
        self.env['sports.treatment.note'].sudo().create({
            'patient_id': self.player.id, 'user_id': self.other.id,
            'note': 'Cross-team note', 'date': '2026-03-10',
        })
        self.env.flush_all()
        self._login_tp()
        resp = self.url_open(f'/my/patient/notes?patient_id={self.player.id}')
        self.assertEqual(resp.status_code, 200, "notes view must not 500 on a cross-user author")
        self.assertIn('Cross Team Therapist', resp.text, "the note author's name should render")

    def test_activity_detail_other_assignee(self):
        act = self.env['mail.activity'].sudo().create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': 'Cross-team activity', 'user_id': self.other.id,
        })
        self.env.flush_all()
        self._login_tp()
        resp = self.url_open(f'/my/activity/{act.id}')
        self.assertEqual(resp.status_code, 200, "activity detail must not 500 on a cross-user assignee")
        self.assertIn('Cross Team Therapist', resp.text, "the assignee name should render")
