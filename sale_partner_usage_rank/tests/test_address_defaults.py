# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Delivery and Invoice Address default to the most-used address.

Exercised through ``odoo.tests.Form`` on a new sales order.

Acceptance criteria:

1. Setting the Customer contact sets Delivery Address to the address used
   most often with that contact on earlier orders, even one under another
   company (a drop-ship site).
2. If that contact has no earlier orders, it is the most-used delivery
   address (``sale_shipping_rank``) within the contact's company.
3. If no address in the company has been used either, it is Odoo's
   standard choice (``address_get``).
4. 1-3 apply to Invoice Address with invoice usage.
5. Ties at a tier go to the address used on the most recent order.
6. Changing the Customer contact re-applies the default for the new one.
7. A Delivery or Invoice Address picked by hand is kept as long as the
   Customer contact is unchanged.
8. Archived addresses are never chosen as defaults.
"""
from odoo.tests import tagged

from .common import SalePartnerUsageRankCase


@tagged("post_install", "-at_install")
class TestAddressDefaults(SalePartnerUsageRankCase):

    def test_contact_tier(self):
        """AC 1"""

    def test_company_tier(self):
        """AC 2"""

    def test_core_fallback(self):
        """AC 3"""

    def test_invoice_address(self):
        """AC 4"""

    def test_tie_most_recent(self):
        """AC 5"""

    def test_contact_change_reapplies(self):
        """AC 6"""

    def test_manual_pick_kept(self):
        """AC 7"""

    def test_archived_never_default(self):
        """AC 8"""
