"""Task 1795, review round 2 (2026-11-27) — a client who opens a stock
portal page by URL is sent back into the client app. Synthetic fixtures
only.

Acceptance criteria covered here (the bookings addon covers
``/my/appointments`` and ``/my/bookings/calendar``):

* UC-R1 ``/my/invoices`` (and its pages) -> ``/my/home`` for a client.
* UC-R2 Unchanged for a therapist (staff app) and for an internal user
  without an app: no redirect to the app home.
"""
from urllib.parse import urlsplit

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestClientRedirects1795(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_plain = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Internal Nobody', 'login': 'pc.inobody.r@example.com',
            'password': 'pc-inobody-r1795',
            'group_ids': [Command.set([cls.env.ref('base.group_user').id])],
        })

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _target(self, url):
        resp = self.url_open(url, allow_redirects=False)
        if resp.status_code in (301, 302, 303):
            return urlsplit(resp.headers['Location']).path
        return resp.status_code

    # -- UC-R1 -----------------------------------------------------------
    def test_client_invoices_to_home(self):
        self._login_plain()
        for url in ('/my/invoices', '/my/invoices/page/2', '/my/invoices?filterby=zzz'):
            self.assertEqual(self._target(url), '/my/home', url)

    # -- UC-R2 -----------------------------------------------------------
    def test_staff_and_no_app_unchanged(self):
        for login in (self._login_tp, lambda: self.authenticate('pc.inobody.r@example.com', 'pc-inobody-r1795')):
            login()
            self.assertNotEqual(self._target('/my/invoices'), '/my/home')
        # Switch off: the client gets the stock page too.
        self._switch(False)
        self._login_plain()
        self.assertEqual(self._target('/my/invoices'), 200)
