"""Task 1540 — browser tour of the bookings pages on the app shell (glue
addon), at phone width and on a laptop: the list shows the booking, the
calendar renders it from the shared component and shows its details.
Visual layout stays UNVERIFIED here (dev-review click-through)."""
from odoo.tests import tagged

from .common import BookingsShellCommon


class _BookingsTourCommon(BookingsShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')


@tagged('post_install', '-at_install')
class TestBookingsShellTourPhone(_BookingsTourCommon):
    browser_size = '390x844'

    def test_bookings_phone(self):
        self.start_tour('/my/bookings', 'sc_1540_bookings', login='bk.tp@example.com')


@tagged('post_install', '-at_install')
class TestBookingsShellTourLaptop(_BookingsTourCommon):
    browser_size = '1366x768'

    def test_bookings_laptop(self):
        self.start_tour('/my/bookings', 'sc_1540_bookings', login='bk.tp@example.com')
