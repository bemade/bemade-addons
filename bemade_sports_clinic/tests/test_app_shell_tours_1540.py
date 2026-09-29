"""Task 1540 — browser tours of the P3 shell pages (static/tests/tours/
sc_app_p3_tours.js), at phone width (390 px) and on a laptop (1366 px).
Synthetic fixtures only.

Acceptance criteria covered here (AC3 / AC6 in a browser):

* UC-T1 (AC3) Clinic list -> clinic -> a waiting-list row set to « Arrivé »
  in place, without a page reload, saved on the server -> the patient's file
  -> a note added from the docked form (linked to the clinic) -> the injury
  sheet loads the unchanged fragment.

A second session changing the list (the 20 s live update), the visual
layout, both themes and both navigation modes stay UNVERIFIED here — the
dev-review click-through covers them.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common


class _Tour1540Common(Clinic1540Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')

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

    def test_clinic_phone(self):
        self.start_tour('/my/clinics', 'sc_1540_clinic', login='pc.tp@example.com')
        self._check_clinic_tour()


@tagged('post_install', '-at_install')
class TestAppShellToursLaptop1540(_Tour1540Common):
    browser_size = '1366x768'

    def test_clinic_laptop(self):
        self.start_tour('/my/clinics', 'sc_1540_clinic', login='pc.tp@example.com')
        self._check_clinic_tour()
