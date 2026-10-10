"""Task 1538 — the app shell for INTERNAL clinic users (owner decision
2026-09-27: an internal lead therapist on the sideline wants the mobile
interface). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-N1 An internal therapist resolves through the SAME resolver to
  ``internal`` + ``therapist`` (+ ``head_therapist`` from a staff row); the
  templates do not branch on internal / share.
* UC-N2 Switch ON: /my/home and /my/teams render in the shell for the
  internal therapist, with « Clinique »; « Plus » offers the back-end link
  (/odoo), visible to the ``internal`` role only (a portal therapist never
  gets it).
* UC-N3 Switch OFF: the internal user's portal is today's (legacy markers).
* UC-N4 An internal user WITHOUT any clinic role keeps the stock portal even
  with the switch on.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellInternal1538(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        user_g = env.ref('base.group_user').id
        clinic_user_g = env.ref('bemade_sports_clinic.group_sports_clinic_user').id
        itp_g = env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional').id
        # The realistic internal lead therapist: clinic « Internal User » +
        # internal treatment professional. (An internal user holding ONLY the
        # TP group already gets a 403 on today's /my/home — no read on
        # sports.team.staff — which this task does not change.)
        cls.itp = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal TP', 'login': 'pc.itp@example.com', 'password': 'pc-itp-1538',
            'group_ids': [Command.set([user_g, clinic_user_g, itp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.itp.partner_id.id,
            'role': 'head_therapist',
        })
        cls.internal_plain = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal Plain', 'login': 'pc.iplain@example.com',
            'password': 'pc-iplain-1538',
            'group_ids': [Command.set([user_g])],
        })

    def _login_itp(self):
        self.authenticate('pc.itp@example.com', 'pc-itp-1538')

    # -- UC-N1 -----------------------------------------------------------
    def test_internal_therapist_roles(self):
        roles = self.itp._sc_app_roles()
        self.assertTrue({'internal', 'therapist', 'head_therapist'} <= roles)
        self.assertNotIn('coach', roles)

    # -- UC-N2 -----------------------------------------------------------
    def test_switch_on_internal_therapist_gets_shell(self):
        self._switch(True)
        self._login_itp()
        text, tree = self._get('/my/home')
        self.assertIsNotNone(self._shell(tree))
        self.assertNotIn('o_portal_my_home', text)
        tabs = self._nav_keys(tree, 'o_sc_tabs')
        self.assertIn('notepad', tabs)
        self.assertEqual(tabs[-1], 'more')
        self.assertIn('clinic', self._nav_keys(tree, 'o_sc_rail_nav'))
        self.assertIn('PC Team A', text)
        self.assertTrue(tree.xpath('//*[@data-sc-section="home.clinic_teaser"]'))
        _text, tree = self._get('/my/teams')
        self.assertIsNotNone(self._shell(tree))
        self.assertTrue(tree.xpath('//a[@data-sc-team-id="%s"]' % self.team_a.id))

    def test_backend_link_internal_only(self):
        self._switch(True)
        self._login_itp()
        _text, tree = self._get('/my/app/more')
        backend = tree.xpath('//main//a[@data-sc-nav-key="backend"]')
        self.assertTrue(backend)
        self.assertEqual(backend[0].get('href'), '/odoo')
        self._login_tp()
        _text, tree = self._get('/my/app/more')
        self.assertFalse(tree.xpath('//a[@data-sc-nav-key="backend"]'))

    # -- UC-N3 -----------------------------------------------------------
    def test_switch_off_internal_keeps_legacy(self):
        self._login_itp()
        text, tree = self._get('/my/home')
        self.assertIn('o_portal_my_home', text)
        self.assertIsNone(self._shell(tree))
        text, tree = self._get('/my/teams')
        self.assertIn('o_sc_teams_sort', text)
        self.assertIsNone(self._shell(tree))

    # -- UC-N4 -----------------------------------------------------------
    def test_internal_without_clinic_role_keeps_stock_portal(self):
        self._switch(True)
        self.assertEqual(self.internal_plain._sc_app_roles(), frozenset({'internal'}))
        self.authenticate('pc.iplain@example.com', 'pc-iplain-1538')
        text, tree = self._get('/my/home')
        self.assertIn('o_portal_my_home', text)
        self.assertIsNone(self._shell(tree))
