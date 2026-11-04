"""Task 1617 — the timesheets filters panel in a browser
(static/tests/tours/sc_timesheet_filters_1617_tours.js). Synthetic fixtures
only.

Acceptance criteria covered here (laptop 1366 px and phone 360 px):

* AC-3 The panel is open on arrival; the list header (sort) still shows on
  the first screen (phone: its top within the 740 px viewport) without a
  sideways scroll; clicking « Filters » collapses it; the next visit opens
  it again (no remembered state); a filter change applies the filters and
  the panel is open after the reload.

The look in both themes stays UNVERIFIED here — the dev-review
click-through covers it.
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


class _TimesheetFiltersTourMixin:

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param(
            'bemade_sports_clinic.app_shell_enabled', 'True')

    def test_filters_open(self):
        self.start_tour('/my/sc/timesheets', 'sc_1617_timesheet_filters', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestTimesheetFiltersToursLaptop1617(_TimesheetFiltersTourMixin, AppShellCommon):
    browser_size = '1366x768'
    allow_inherited_tests_method = True


@tagged('post_install', '-at_install')
class TestTimesheetFiltersToursPhone1617(_TimesheetFiltersTourMixin, AppShellCommon):
    browser_size = '360x740'
    allow_inherited_tests_method = True
