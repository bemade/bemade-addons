"""Task 1542 — browser tours of the portal app shell (the addon's first tour
harness; static/tests/tours/sc_app_shell_tours.js, web.assets_tests).
Synthetic fixtures only.

Acceptance criteria covered here (AC6, with AC1 / AC3 / AC5 in a browser):

* UC-B1 Navigation: bottom tabs at phone width (390 px), left rail on a
  laptop (1366 px).
* UC-B2 The app-bar theme toggle switches in place (no reload) and persists;
  « Plus › Navigation › Fil d'Ariane » gives the crumb row on a sub-page.
* UC-B3 Team tabs switch in place and keep ?tab= in the address bar; the
  digest-history sheet opens and lazy-loads.
* UC-B4 (AC3) Announcement draft: type -> leave -> return -> « Brouillon
  restauré » with the text -> Publier -> the draft is gone and EXACTLY ONE
  history row was created; logout clears the device drafts.
* UC-B5 (AC5) The install page renders its per-device steps.
* UC-B6 (AC1) Kill switch: a service worker registered while the switch is
  on unregisters itself once the switch is off — task 1543: the new "/"
  registration AND an old P1b "/my/" one of the same script.

Visual layout, both themes at both widths, a real install and real offline
behaviour stay UNVERIFIED here — the dev-review click-through covers them.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _TourCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')
        cls.team_url = '/my/team?team_id=%s' % cls.team_a.id


@tagged('post_install', '-at_install')
class TestAppShellToursPhone1542(_TourCommon):
    browser_size = '390x844'

    def test_nav_phone(self):
        self.start_tour('/my/teams', 'sc_1542_nav_phone', login='pc.coach@example.com')

    def test_team_tabs_phone(self):
        self.start_tour(self.team_url, 'sc_1542_team_tabs', login='pc.tp@example.com')

    def test_announcement_draft(self):
        history = self.env['sports.team.note.history'].search_count(
            [('team_id', '=', self.team_a.id)])
        self.start_tour(self.team_url, 'sc_1542_announcement_draft', login='pc.tp@example.com')
        self.team_a.invalidate_recordset()
        self.assertEqual(self.team_a.announcement, 'Tour 1542 synthetic draft')
        self.assertEqual(self.env['sports.team.note.history'].search_count(
            [('team_id', '=', self.team_a.id)]), history + 1)

    def test_logout_clears_drafts(self):
        self.start_tour(self.team_url, 'sc_1542_logout_clears_drafts', login='pc.tp@example.com')
        self.team_a.invalidate_recordset()
        self.assertFalse(self.team_a.announcement)

    def test_install_page(self):
        self.start_tour('/my/app/install', 'sc_1542_install_page', login='pc.coach@example.com')


@tagged('post_install', '-at_install')
class TestAppShellToursLaptop1542(_TourCommon):
    browser_size = '1366x768'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # An internal head therapist who may also toggle system parameters
        # (the kill-switch tour turns the switch off mid-tour).
        cls.itp_admin = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'T1542 Internal Admin TP', 'login': 't1542.admin@example.com',
            'password': 't1542-admin-pass',
            'group_ids': [Command.set([
                env.ref('base.group_system').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_user').id,
                env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id,
            ])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.itp_admin.partner_id.id,
            'role': 'head_therapist',
        })

    def test_nav_laptop(self):
        self.start_tour('/my/teams', 'sc_1542_nav_laptop', login='pc.tp@example.com')

    def test_prefs_theme_and_crumbs(self):
        self.start_tour('/my/home', 'sc_1542_prefs', login='pc.coach@example.com')
        self.assertEqual(self.coach.sc_theme, 'light')
        self.assertEqual(self.coach.sc_nav_mode, 'crumbs')

    def test_team_tabs_internal_therapist(self):
        self.start_tour(self.team_url, 'sc_1542_team_tabs', login='t1542.admin@example.com')

    def test_sw_kill_switch(self):
        self.start_tour('/my/home', 'sc_1542_sw_kill_switch', login='t1542.admin@example.com')
        self.assertFalse(self.env['ir.config_parameter'].sudo().get_param(
            'bemade_sports_clinic.app_shell_enabled'))
