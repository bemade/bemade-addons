"""Task 1540 — browser tours of the P3 shell pages (static/tests/tours/
sc_app_p3_tours.js), at phone width (390 px) and on a laptop (1366 px).
Synthetic fixtures only.

Acceptance criteria covered here (AC3 / AC6 in a browser):

* UC-T2 Events list -> event -> « Ajouter ma feuille de temps » sheet ->
  one more timesheet, back on the event.
* UC-T3 The shared calendar renders the feed with FullCalendar from the
  lazy bundle (no raw <script src>) and an event opens its page.
* UC-T4 Notepad: a quick note typed (device draft) -> « Ajouter » -> listed,
  the draft gone.
* UC-T1 (AC3) Clinic list -> clinic -> a waiting-list row set to « Arrivé »
  in place, without a page reload, saved on the server -> the patient's file
  -> a note added from the docked form (linked to the clinic) -> the injury
  sheet loads the unchanged fragment.

A second session changing the list (the 20 s live update), the visual
layout, both themes and both navigation modes stay UNVERIFIED here — the
dev-review click-through covers them.
"""
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common


class _Tour1540Common(Clinic1540Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')
        now = fields.Datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
        cls.cal_event = cls.env['sports.event'].create({
            'name': 'SC 1540 Calendar Game', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': now, 'date_end': now + timedelta(hours=2), 'state': 'confirmed',
        })

    def _check_clinic_tour(self):
        rows = self.env['sports.clinic.attendance'].search([
            ('event_id', '=', self.clinic.id), ('patient_id', '!=', False)])
        self.assertIn('arrived', rows.mapped('state'))
        note = self.env['sports.treatment.note'].search([
            ('note', '=', 'Tour 1540 synthetic clinic note')])
        self.assertEqual(len(note), 1)
        self.assertEqual(note.event_id, self.clinic)


@tagged('post_install', '-at_install')
class TestAppShellToursPhone1540(_Tour1540Common):
    browser_size = '390x844'

    def test_event_timesheet_phone(self):
        Timesheet = self.env['sports.event.timesheet']
        domain = [('event_id', '=', self.event.id), ('user_id', '=', self.tp.id)]
        before = Timesheet.search_count(domain)
        self.start_tour('/my/events?no_default_dates=1&event_type=game&team_id=%s&date_to=2026-02-03'
                        % self.team_a.id, 'sc_1540_event_timesheet', login='pc.tp@example.com')
        self.assertEqual(Timesheet.search_count(domain), before + 1)

    def test_notepad_phone(self):
        self.start_tour('/my/notepad', 'sc_1540_notepad', login='pc.tp@example.com')
        self.assertEqual(self.env['sports.quick.note'].sudo().search_count([
            ('note', '=', 'Tour 1540 synthetic quick note'), ('user_id', '=', self.tp.id)]), 1)

    def test_calendar_phone(self):
        self.start_tour('/my/events/calendar', 'sc_1540_calendar', login='pc.coach@example.com')

    def test_clinic_phone(self):
        self.start_tour('/my/clinics', 'sc_1540_clinic', login='pc.tp@example.com')
        self._check_clinic_tour()


@tagged('post_install', '-at_install')
class TestAppShellToursLaptop1540(_Tour1540Common):
    browser_size = '1366x768'

    def test_calendar_laptop(self):
        self.start_tour('/my/events/calendar', 'sc_1540_calendar', login='pc.tp@example.com')

    def test_clinic_laptop(self):
        self.start_tour('/my/clinics', 'sc_1540_clinic', login='pc.tp@example.com')
        self._check_clinic_tour()
