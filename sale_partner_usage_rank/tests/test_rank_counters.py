# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Usage counters stay equal to the number of orders using each partner.

Acceptance criteria:

1. Creating a sales order adds 1 to ``sale_contact_rank`` of its Customer,
   ``sale_shipping_rank`` of its Delivery Address and ``sale_invoice_rank``
   of its Invoice Address. One partner in several slots is counted in each.
2. Changing one of those fields on an order moves 1 from the old partner's
   counter to the new partner's counter, and leaves the other counters alone.
3. Deleting an order takes 1 off each of its three partners' counters.
4. State does not matter: a quotation counts, and confirming or cancelling
   it does not change any counter.
5. Creating or changing several orders in one call counts each order.
6. The install hook sets every counter to the actual count from existing
   orders, overwriting any stale value, and partners with no orders get 0.
"""
from odoo.tests import tagged

from ..hooks import _backfill_sale_usage_ranks
from .common import SalePartnerUsageRankCase


@tagged("post_install", "-at_install")
class TestRankCounters(SalePartnerUsageRankCase):

    def test_create_counts_each_slot(self):
        """AC 1"""
        self._order(self.jason, self.acme_site_a, self.acme_billing)
        self._order(self.jason)
        self.assertRanks(self.jason, 2, 1, 1)
        self.assertRanks(self.acme_site_a, 0, 1, 0)
        self.assertRanks(self.acme_billing, 0, 0, 1)

    def test_change_moves_count(self):
        """AC 2"""
        order = self._order(self.jason, self.acme_site_a, self.acme_billing)
        order.partner_shipping_id = self.acme_site_b
        self.assertRanks(self.acme_site_a, 0, 0, 0)
        self.assertRanks(self.acme_site_b, 0, 1, 0)
        self.assertRanks(self.jason, 1, 0, 0)
        self.assertRanks(self.acme_billing, 0, 0, 1)
        order.write({
            "partner_id": self.mary.id,
            "partner_shipping_id": self.acme_site_b.id,
            "partner_invoice_id": self.acme_billing.id,
        })
        self.assertRanks(self.jason, 0, 0, 0)
        self.assertRanks(self.mary, 1, 0, 0)
        self.assertRanks(self.acme_site_b, 0, 1, 0)

    def test_unlink_decrements(self):
        """AC 3"""
        keep = self._order(self.jason, self.acme_site_a, self.acme_billing)
        drop = self._order(self.jason, self.acme_site_a, self.acme_billing)
        drop.unlink()
        self.assertRanks(self.jason, 1, 0, 0)
        self.assertRanks(self.acme_site_a, 0, 1, 0)
        self.assertRanks(self.acme_billing, 0, 0, 1)
        keep.unlink()
        self.assertRanks(self.jason, 0, 0, 0)

    def test_state_does_not_matter(self):
        """AC 4"""
        order = self._order(self.jason, self.acme_site_a, self.acme_billing)
        self.assertRanks(self.jason, 1, 0, 0)
        order.action_confirm()
        self.assertRanks(self.jason, 1, 0, 0)
        self.assertRanks(self.acme_site_a, 0, 1, 0)
        order._action_cancel()
        self.assertRanks(self.jason, 1, 0, 0)
        self.assertRanks(self.acme_site_a, 0, 1, 0)
        self.assertRanks(self.acme_billing, 0, 0, 1)

    def test_batch_create_and_write(self):
        """AC 5"""
        vals = {
            "partner_id": self.jason.id,
            "partner_shipping_id": self.acme_site_a.id,
            "partner_invoice_id": self.acme_billing.id,
        }
        orders = self.env["sale.order"].create([vals] * 3)
        self.assertRanks(self.jason, 3, 0, 0)
        self.assertRanks(self.acme_site_a, 0, 3, 0)
        orders[:2].write({"partner_shipping_id": self.acme_site_b.id})
        self.assertRanks(self.acme_site_a, 0, 1, 0)
        self.assertRanks(self.acme_site_b, 0, 2, 0)

    def test_backfill_hook(self):
        """AC 6"""
        self._order(self.jason, self.acme_site_a, self.acme_billing)
        self._order(self.jason, self.acme_site_a, self.acme_billing)
        self.env.cr.execute(
            "UPDATE res_partner SET sale_contact_rank = 0, sale_shipping_rank = 7,"
            " sale_invoice_rank = 0 WHERE id IN %s",
            [(self.jason.id, self.acme_site_a.id, self.mary.id)],
        )
        self.env["res.partner"].invalidate_model()
        _backfill_sale_usage_ranks(self.env)
        self.assertRanks(self.jason, 2, 0, 0)
        self.assertRanks(self.acme_site_a, 0, 2, 0)
        self.assertRanks(self.acme_billing, 0, 0, 2)
        self.assertRanks(self.mary, 0, 0, 0)
