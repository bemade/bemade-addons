# Part of Bemade Sports Clinic. See LICENSE file for full copyright and licensing details.
"""Timesheet home-card override targeting (2026-08-31 prod incident #2).

Acceptance criteria
===================
* The override that re-points the stock hr_timesheet home card must touch ONLY
  that card. Its old bare ``//t[@t-set='title']`` xpaths matched the FIRST
  t-set in the COMBINED portal_my_home arch — the account_payment overdue
  ALERT banner (priority 20) — turning it into a « 266 Past Timesheets /
  Pay Now » banner for every TP with timesheets.
* The overdue banner must keep its own placeholder (``overdue_invoice_count``)
  and the timesheet card must carry ``/my/sc/timesheets`` +
  ``event_timesheets_count``.
"""
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestHomeTimesheetCard(PortalCovCommon):

    def _home_html(self):
        self.authenticate('pc.tp@example.com', 'pc-tp')
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_overdue_banner_keeps_its_own_placeholder(self):
        html = self._home_html()
        if 'account_payment' not in self.env['ir.module.module']._installed():
            self.skipTest('account_payment not installed')
        self.assertIn('data-placeholder_count="overdue_invoice_count"', html,
                      "the overdue-invoices banner lost its counter to the "
                      "timesheet override (bare //t[@t-set] xpath collision)")

    def test_timesheet_card_repointed(self):
        html = self._home_html()
        self.assertIn('/my/sc/timesheets', html)
        self.assertIn('data-placeholder_count="event_timesheets_count"', html)
