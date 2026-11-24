# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): browser tours of the installable app, with this addon
alone (static/tests/tours/pk_pwa_tours.js). Synthetic users only.

* UC-B1 The install page renders its per-device steps; the « installed »
  state stays hidden in a plain browser tab.
* UC-B2 Kill switch: the worker registered by a shell page (scope ``/``,
  its ``pk-app-shell-*`` cache precached) and an older ``/my/``
  registration of the same script are all unregistered once the switch is
  off, from a stock portal page.
"""
from odoo.tests import HttpCase, new_test_user, tagged

from .common import pk_pwa_shell


@tagged('post_install', '-at_install')
class TestPkPwaTours(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(cls.env, login='pk_p6_tour', groups='base.group_portal', lang='en_US')

    def _shell(self, roles):
        shell = pk_pwa_shell(self.env, roles=roles)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)

    def test_install_page(self):
        self._shell({'member': {'groups': ('base.group_portal',)}})
        self.start_tour('/my/app/install', 'pk_pwa_install_page', login='pk_p6_tour')

    def test_sw_kill_switch(self):
        # The administrator holds the app role (it turns the switch off mid-tour).
        self._shell({'member': {'groups': ('base.group_user',)}})
        self.start_tour('/my/app/more', 'pk_pwa_sw_kill_switch', login='admin')
        self.assertFalse(self.env['ir.config_parameter'].sudo().get_param('bemade_portal_kit.enabled'))
