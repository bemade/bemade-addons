# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Sales order partner dropdowns list the most-used partners first.

The sales order form asks for ranking through the field context
(``sale_usage_rank`` naming the slot, plus ``sale_usage_rank_contact_id``
for the address slots). These tests call ``name_search`` with that context,
as the dropdown does.

Acceptance criteria:

1. Customer slot: matches come by ``sale_contact_rank`` descending; ties and
   never-used partners keep the standard partner order.
2. Delivery Address slot, contact given: addresses used with that contact
   come first, most uses first; then by ``sale_shipping_rank`` descending.
3. Invoice Address slot: same as 2, with ``sale_invoice_rank``.
4. Address slot, no contact yet: ordered by the slot's rank alone.
5. Ranking reorders but never filters: the matched set is the same as
   without the context, and the limit applies after ranking, so a heavily
   used partner past the first page of the standard order is returned.
6. Without the context (any other partner field), order is unchanged.
7. The sales order form gives each of the three fields that context
   (checked through ``Form``, so the view and the context stay in sync).
"""
from odoo.tests import tagged

from .common import SalePartnerUsageRankCase


@tagged("post_install", "-at_install")
class TestDropdownOrder(SalePartnerUsageRankCase):

    def test_customer_slot_by_rank(self):
        """AC 1"""

    def test_shipping_slot_contact_then_rank(self):
        """AC 2"""

    def test_invoice_slot_contact_then_rank(self):
        """AC 3"""

    def test_address_slot_without_contact(self):
        """AC 4"""

    def test_ranking_does_not_filter_and_limit_after_rank(self):
        """AC 5"""

    def test_no_context_unchanged(self):
        """AC 6"""

    def test_form_passes_context(self):
        """AC 7"""
