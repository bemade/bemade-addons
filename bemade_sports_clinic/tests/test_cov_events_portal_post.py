from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovEventsPortalPost(PortalCovCommon):
    """POST-route sampling for the events portal (add timesheet / cancel / create)."""

    # ---- add_timesheet ----

    def test_add_timesheet_happy(self):
        self._login_tp()
        before = self.env['sports.event.timesheet'].search_count([
            ('event_id', '=', self.event.id), ('user_id', '=', self.tp.id)])
        resp = self.url_open(f'/my/event/{self.event.id}/timesheet/add',
                             data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 200)
        after = self.env['sports.event.timesheet'].search_count([
            ('event_id', '=', self.event.id), ('user_id', '=', self.tp.id)])
        self.assertEqual(after, before + 1, "a timesheet should have been created")

    def test_add_timesheet_denied_for_coach(self):
        # Coaches are not therapists -> not allowed to add timesheets.
        self._login_coach()
        resp = self.url_open(f'/my/event/{self.event.id}/timesheet/add',
                             data={'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 403)

    # ---- cancel_event ----

    def test_cancel_event_happy(self):
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}/cancel', data={
            'csrf_token': self._csrf(), 'cancel_reason': 'Field flooded',
        })
        self.assertEqual(resp.status_code, 200)
        self.event.invalidate_recordset(['state'])
        self.assertEqual(self.event.state, 'cancelled')

    def test_cancel_event_requires_reason(self):
        self._login_tp()
        self.url_open(f'/my/event/{self.event.id}/cancel', data={'csrf_token': self._csrf()})
        self.event.invalidate_recordset(['state'])
        self.assertNotEqual(self.event.state, 'cancelled',
                            "cancellation without a reason must not cancel the event")

    # ---- create_event_submit ----

    def test_create_event_happy(self):
        self._login_tp()
        resp = self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(),
            'name': 'POST Created Event',
            'team_id': self.team_a.id,
            'event_type': 'game',
            'date_start': '2026-03-01T10:00',
            'date_end': '2026-03-01T12:00',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.env['sports.event'].search([('name', '=', 'POST Created Event')]),
                        "the event should have been created")

    def test_detail_shows_assigned_staff_for_portal(self):
        # The event detail page must show assigned staff to a portal user
        # (reads via event_sudo since portal can't read other res.users).
        other_tp = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Detail Staff Person', 'login': 'pc.tp.detail@example.com', 'password': 'x',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': other_tp.partner_id.id, 'role': 'therapist',
        })
        self.event.sudo().write({'assigned_staff_ids': [Command.set([other_tp.id])]})
        self.env.flush_all()  # ensure the assignment hits the DB before the HTTP read
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Detail Staff Person', resp.text,
                      "the assigned staff member's name should appear on the event detail page")

    def test_edit_form_prechecks_team_for_portal(self):
        # Regression: editing an event whose team the portal user does NOT staff
        # must still render that team as a pre-checked option (it read team_ids
        # non-sudo, so the team dropped out and saving failed with no team).
        ev = self.env['sports.event'].create({
            'name': 'Cross Team Event',
            'team_ids': [Command.set([self.team_b.id])],
            'date_start': '2026-03-05 10:00:00', 'date_end': '2026-03-05 12:00:00',
            'state': 'confirmed',
        })
        self.env.flush_all()  # ensure the event hits the DB before the HTTP read
        self._login_tp()  # tp staffs team_a, NOT team_b
        resp = self.url_open(f'/my/event/{ev.id}/edit')
        self.assertEqual(resp.status_code, 200)
        self.assertRegex(resp.text, r'value="%s"[^>]*checked' % self.team_b.id,
                         "the event's current team should be a pre-checked option")

    def test_edit_form_prechecks_assigned_staff_for_portal(self):
        # Regression: the edit form pre-checks the assigned-staff checkboxes by
        # reading assigned_staff_ids. Done non-sudo, a portal user (who can't read
        # other res.users) saw NO staff selected even when staff was assigned
        # (the list-view card showed it because that path sudoes the read).
        other_tp = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Darcie Hum', 'login': 'pc.tp.dh@example.com', 'password': 'x',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': other_tp.partner_id.id, 'role': 'therapist',
        })
        self.event.sudo().write({'assigned_staff_ids': [Command.set([other_tp.id])]})
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}/edit')
        self.assertEqual(resp.status_code, 200)
        # The assigned staff member's checkbox must render as checked.
        self.assertRegex(resp.text, r'value="%s"[^>]*checked' % other_tp.id,
                         "the assigned staff's checkbox should be pre-checked in the edit form")

    def test_create_event_with_other_assigned_staff(self):
        # Regression: a portal TP assigning ANOTHER user as staff must succeed.
        # Writing assigned_staff_ids (m2m to res.users) non-sudo would otherwise
        # AccessError because portal users can't read other res.users records.
        other_tp = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Other TP', 'login': 'pc.tp.other@example.com', 'password': 'x',
            'group_ids': [Command.set([
                self.env.ref('base.group_portal').id,
                self.env.ref('bemade_sports_clinic.group_portal_treatment_professional').id,
            ])],
        })
        self.env['sports.team.staff'].create({
            'team_id': self.team_a.id, 'partner_id': other_tp.partner_id.id, 'role': 'therapist',
        })
        self._login_tp()
        resp = self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(),
            'name': 'Event With Other Staff',
            'team_id': self.team_a.id, 'event_type': 'game',
            'date_start': '2026-03-02T10:00', 'date_end': '2026-03-02T12:00',
            'assigned_staff_ids': other_tp.id,
        })
        self.assertEqual(resp.status_code, 200)
        ev = self.env['sports.event'].search([('name', '=', 'Event With Other Staff')])
        self.assertTrue(ev, "the event should have been created")
        self.assertIn(other_tp, ev.assigned_staff_ids,
                      "the other user should be assigned as staff")

    def test_create_event_missing_name(self):
        self._login_tp()
        before = self.env['sports.event'].search_count([])
        resp = self.url_open('/my/event/create/submit', data={
            'csrf_token': self._csrf(),
            'team_id': self.team_a.id,
            'date_start': '2026-03-01T10:00', 'date_end': '2026-03-01T12:00',
        })
        self.assertEqual(resp.status_code, 200, "missing name must re-render the form, not 500")
        self.assertEqual(self.env['sports.event'].search_count([]), before,
                         "no event should be created without a name")

    # ---- save_event ----

    def test_save_event_happy(self):
        self._login_tp()
        resp = self.url_open(f'/my/event/{self.event.id}/save', data={
            'csrf_token': self._csrf(), 'name': 'Saved Event Name',
        })
        self.assertEqual(resp.status_code, 200)
        self.event.invalidate_recordset(['name'])
        self.assertEqual(self.event.name, 'Saved Event Name')

    # ---- create_venue_ajax (jsonrpc) ----

    def test_create_venue_ajax_happy(self):
        self._login_tp()
        result = self._jsonrpc('/my/venue/create', name='JSONRPC Arena')
        self.assertTrue(result.get('success'))
        self.assertTrue(self.env['res.partner'].search([
            ('name', '=', 'JSONRPC Arena'), ('is_venue', '=', True)]))

    def test_create_venue_ajax_requires_name(self):
        self._login_tp()
        result = self._jsonrpc('/my/venue/create', name='')
        self.assertFalse(result.get('success'))
