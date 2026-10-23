"""Task 1622 — browser tours: the activities page opened from the app-bar
clock has a back arrow (static/tests/tours/sc_clock_back_1622_tours.js).
Synthetic fixtures only.

Acceptance criteria:

* UC-CT1 (phone 360 px, laptop 1366 px) Player page → clock → activities:
  the back arrow shows (no logo), stays after switching to the All tab, and
  returns to the player page (history.back()).
* UC-CT2 (phone, laptop) Deep link to the activities page with the clock's
  origin and no in-app history in the tab: the arrow's href (the origin
  player page) is where back goes.
"""
from urllib.parse import quote

from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_clock_back_1622 import Clock1622Common


class _Tours1622(Clock1622Common):

    def _clock_back(self):
        self.start_tour(self.player_url, 'sc_1622_clock_back', login='pc.tp@example.com')

    def _clock_back_deep_link(self):
        url = '/my/activities?sc_clock=1&sc_from=%s' % quote(self.player_url, safe='')
        self.start_tour(url, 'sc_1622_clock_back_deep_link', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestClockBackPhone1622(_Tours1622):
    browser_size = '360x800'

    def test_clock_back(self):
        self._clock_back()

    def test_clock_back_deep_link(self):
        self._clock_back_deep_link()


@tagged('post_install', '-at_install')
class TestClockBackLaptop1622(_Tours1622):
    browser_size = '1366x768'

    def test_clock_back(self):
        self._clock_back()

    def test_clock_back_deep_link(self):
        self._clock_back_deep_link()
