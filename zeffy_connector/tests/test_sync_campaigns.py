# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Use case: Zeffy campaigns are known in Odoo.

Acceptance criteria
- Each Zeffy campaign becomes one ``zeffy.campaign`` (title, type, status,
  URL, goal and amount raised in currency units, not cents).
- It is linked to a UTM campaign of the same name, created when missing.
- Re-running the synchronization creates nothing new and picks up changes.
"""

from odoo.tests import tagged

from .common import ZeffyCase, make_campaign


@tagged("post_install", "-at_install")
class TestZeffySyncCampaigns(ZeffyCase):
    def test_campaign_is_created_with_values(self):
        data = make_campaign(title="Spring Gala", target=1500000, goal_amount=1500000, volume=420050)
        self.api.campaigns = [data]
        self.sync()
        campaign = self.Campaign.search([("zeffy_id", "=", data["id"])])
        self.assertEqual(len(campaign), 1)
        self.assertEqual(campaign.name, "Spring Gala")
        self.assertEqual(campaign.campaign_type, "donation_form")
        self.assertEqual(campaign.status, "active")
        self.assertEqual(campaign.goal_amount, 15000.0)
        self.assertEqual(campaign.amount_raised, 4200.50)
        self.assertEqual(campaign.currency_id, self.cad)
        self.assertEqual(campaign.company_id, self.company)
        self.assertEqual(campaign.utm_campaign_id.name, "Spring Gala")

    def test_existing_utm_campaign_is_reused(self):
        utm = self.env["utm.campaign"].create({"name": "Golf Tournament"})
        self.api.campaigns = [make_campaign(title="Golf Tournament")]
        self.sync()
        self.assertEqual(self.Campaign.search([]).utm_campaign_id, utm)

    def test_resync_is_idempotent_and_updates(self):
        data = make_campaign(title="Telethon", volume=1000)
        self.api.campaigns = [data]
        self.sync()
        data["volume"] = 9900
        self.sync()
        campaign = self.Campaign.search([])
        self.assertEqual(len(campaign), 1)
        self.assertEqual(campaign.amount_raised, 99.0)
        self.assertEqual(self.env["utm.campaign"].search_count([("name", "=", "Telethon")]), 1)
