"""Task 1647 — tab bars fit a phone's width; the count pill before the
label (static/tests/tours/sc_tabs_fit_1647_tours.js). Synthetic fixtures
only.

Acceptance criteria covered here:

* AC-1 390 px and 375 px: the player page's five tabs and the Activities
  count pill are within the viewport, no sideways scroll, « Docs » shown
  (« Documents » kept as the title), no label cut.
* AC-2 Every width: the pill precedes the label in the DOM; laptop shows
  « Documents » in full.

The real iPhone stays UNVERIFIED until /dev-review.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_injury_quick_tours_1604 import QuickToursCommon


class _Tabs1647(QuickToursCommon):

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id


@tagged('post_install', '-at_install')
class TestTabsFit390_1647(_Tabs1647):
    browser_size = '390x844'

    def test_player_phone(self):
        self.start_tour(self._url(), 'sc_1647_player_phone', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestTabsFit375_1647(_Tabs1647):
    browser_size = '375x812'

    def test_player_phone(self):
        self.start_tour(self._url(), 'sc_1647_player_phone', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestTabsFitLaptop1647(_Tabs1647):
    browser_size = '1366x768'

    def test_player_laptop(self):
        self.start_tour(self._url(), 'sc_1647_player_laptop', login='pc.tp@example.com')
