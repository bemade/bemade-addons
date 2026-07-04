"""Event-detail timesheet confidentiality (dev-review finding, 2026-07-04).

Acceptance criteria:
- A TP assigned to an event sees ONLY their own timesheets on the event detail
  page (tab renamed 'My Timesheets'); other TPs' rows never render.
- A TP who is NOT assigned to the event sees neither the My Timesheets tab nor
  the 'Add My Timesheet' button/modal.
"""
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestEventDetailTimesheetConfidentiality(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC TP Two', 'login': 'pc.tp2@example.com', 'password': 'pc-tp2xx',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist',
        })
        # Second TP is also assigned to the shared event and has a timesheet on it.
        cls.event.write({'assigned_staff_ids': [Command.link(cls.tp2.id)]})
        cls.ts_tp2 = env['sports.event.timesheet'].create({
            'event_id': cls.event.id, 'user_id': cls.tp2.id,
        })

    def test_assigned_tp_sees_only_own_timesheets(self):
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('My Timesheets', resp.text)
        # Own row renders in the timesheet table (name cell markup)...
        self.assertIn('<span>PC TP</span>', resp.text)
        # ...but the other TP's row must not (their name may still appear in the
        # Assigned Staff panel, which uses different markup).
        self.assertNotIn('<span>PC TP Two</span>', resp.text)

    def test_unassigned_tp_has_no_tab_or_add_button(self):
        self.event.sudo().write({'assigned_staff_ids': [Command.unlink(self.tp.id)]})
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('My Timesheets', resp.text)
        self.assertNotIn('Add My Timesheet', resp.text)
