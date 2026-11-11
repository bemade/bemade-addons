# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Use case: the scheduled action keeps every configured company in sync.

Acceptance criteria
- Only companies with an API key are synchronized.
- A failure for one company is recorded on that company (and its partial
  work rolled back) without stopping the others.
- A successful run records its time and clears the previous error.
"""

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import ZeffyCase, make_campaign


@tagged("post_install", "-at_install")
class TestZeffyCron(ZeffyCase):
    def test_cron_isolates_failures(self):
        self.api.campaigns = [make_campaign()]
        broken = self.env["res.company"].create({"name": "Broken NPO", "zeffy_api_key": "wrong-key"})
        unconfigured = self.env["res.company"].create({"name": "No Zeffy"})
        self.company.zeffy_last_sync_error = "old error"
        with mute_logger("odoo.addons.zeffy_connector.models.res_company"):
            self.env["res.company"]._cron_zeffy_sync()
        self.assertTrue(self.company.zeffy_last_sync)
        self.assertFalse(self.company.zeffy_last_sync_error)
        self.assertEqual(self.Campaign.search([]).company_id, self.company)
        self.assertTrue(broken.zeffy_last_sync_error)
        self.assertFalse(broken.zeffy_last_sync)
        self.assertFalse(unconfigured.zeffy_last_sync)
        self.assertFalse(unconfigured.zeffy_last_sync_error)
