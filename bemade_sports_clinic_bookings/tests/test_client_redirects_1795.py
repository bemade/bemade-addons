"""Task 1795, review round 2 (2026-11-27) — a client who opens a stock
booking page by URL is sent to « Rendez-vous ». Synthetic fixtures only.

Acceptance criteria covered here:

* UC-R3 ``/my/appointments``, its pages and filter variants (a bad filter
  too: it was a stock 500) -> ``/my/bookings`` for a client.
* UC-R4 ``/my/bookings/calendar`` -> ``/my/bookings`` for a client.
* UC-R5 Unchanged for a therapist (staff app: the calendar renders, no
  redirect of « My appointments » to « Rendez-vous ») and for a portal
  appointment provider without a clinic role.
"""
from urllib.parse import urlsplit

from odoo import Command
from odoo.tests import tagged

from .test_client_bookings_1795 import TestClientBookings1795


@tagged('post_install', '-at_install')
class TestClientRedirects1795(TestClientBookings1795):

    # The inherited tests run once, in their own class.
    test_own_bookings_only = test_foreign_client_sees_only_theirs = test_empty_state = None
    test_token_links = test_client_home_part = test_book_none_one_two = None
    test_others_unchanged = test_portal_provider_keeps_stock_page = None

    def _target(self, url):
        resp = self.url_open(url, allow_redirects=False)
        if resp.status_code in (301, 302, 303):
            return urlsplit(resp.headers['Location']).path
        return resp.status_code

    # -- UC-R3 / UC-R4 ---------------------------------------------------
    def test_client_redirects(self):
        self._login_client()
        for url in ('/my/appointments', '/my/appointments/page/2', '/my/appointments?filterby=upcoming',
                    '/my/appointments?filterby=zzz', '/my/appointments?sortby=date&groupby=none',
                    '/my/bookings/calendar'):
            self.assertEqual(self._target(url), '/my/bookings', url)

    # -- UC-R5 -----------------------------------------------------------
    def test_staff_control(self):
        self.authenticate('bk.tp@example.com', 'bk-tp-pass')
        self.assertEqual(self._target('/my/bookings/calendar'), 200)
        self.assertNotEqual(self._target('/my/appointments'), '/my/bookings')

    def test_provider_control(self):
        self.apt_type.staff_user_ids = [Command.link(self.other_user.id)]
        self.authenticate('bk.other@example.com', 'bk-other-pass')
        self.assertEqual(self._target('/my/bookings/calendar'), 200)
        self.assertNotEqual(self._target('/my/appointments'), '/my/bookings')
