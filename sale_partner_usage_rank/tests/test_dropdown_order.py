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
from lxml import etree

from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import SalePartnerUsageRankCase


@tagged("post_install", "-at_install")
class TestDropdownOrder(SalePartnerUsageRankCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.zulu_site = cls.env["res.partner"].create({
            "name": "Zulu Site", "type": "delivery", "parent_id": cls.globex.id,
        })
        cls.sites = cls.acme_site_a | cls.acme_site_b | cls.globex_site | cls.zulu_site

    def _suggest(self, partners, slot=None, contact=None, name="", limit=100):
        ctx = {}
        if slot:
            ctx["sale_usage_rank"] = slot
        if contact:
            ctx["default_parent_id"] = contact.id
        Partner = self.env["res.partner"].with_context(**ctx)
        result = Partner.name_search(name, [("id", "in", partners.ids)], limit=limit)
        return [pid for pid, _name in result]

    def test_customer_slot_by_rank(self):
        """AC 1"""
        self._order(self.mary)
        self._order(self.mary)
        self._order(self.jason)
        people = self.acme.child_ids
        standard = self._suggest(people)
        self.assertEqual(
            self._suggest(people, "partner_id"),
            [self.mary.id, self.jason.id]
            + [pid for pid in standard if pid not in (self.mary.id, self.jason.id)],
        )

    def test_shipping_slot_contact_then_rank(self):
        """AC 2"""
        self._order(self.jason, self.acme_site_b)
        for _i in range(3):
            self._order(self.mary, self.acme_site_a)
        self._order(self.mary, self.globex_site)
        self.assertEqual(
            self._suggest(self.sites, "partner_shipping_id", self.jason),
            [self.acme_site_b.id, self.acme_site_a.id, self.globex_site.id, self.zulu_site.id],
        )

    def test_invoice_slot_contact_then_rank(self):
        """AC 3"""
        self._order(self.mary, invoice=self.acme)
        self._order(self.mary, invoice=self.acme)
        self._order(self.jason, invoice=self.acme_billing)
        billing = self.acme | self.acme_billing
        # The standard order puts the company first.
        self.assertEqual(self._suggest(billing), [self.acme.id, self.acme_billing.id])
        self.assertEqual(
            self._suggest(billing, "partner_invoice_id", self.jason),
            [self.acme_billing.id, self.acme.id],
        )

    def test_address_slot_without_contact(self):
        """AC 4"""
        self._order(self.jason, self.acme_site_b)
        for _i in range(3):
            self._order(self.mary, self.acme_site_a)
        self.assertEqual(
            self._suggest(self.acme_site_a | self.acme_site_b, "partner_shipping_id"),
            [self.acme_site_a.id, self.acme_site_b.id],
        )
        self._order(self.mary, invoice=self.acme_billing)
        self._order(self.mary, invoice=self.acme_billing)
        self._order(self.jason, invoice=self.acme)
        self.assertEqual(
            self._suggest(self.acme | self.acme_billing, "partner_invoice_id"),
            [self.acme_billing.id, self.acme.id],
        )

    def test_ranking_does_not_filter_and_limit_after_rank(self):
        """AC 5"""
        self._order(self.mary, self.zulu_site)
        self.assertEqual(
            set(self._suggest(self.sites, "partner_shipping_id")),
            set(self._suggest(self.sites)),
        )
        self.assertEqual(self._suggest(self.sites, limit=1), [self.acme_site_a.id])
        self.assertEqual(
            self._suggest(self.sites, "partner_shipping_id", limit=1), [self.zulu_site.id],
        )
        self.assertEqual(
            self._suggest(self.sites, "partner_shipping_id", name="site", limit=1),
            [self.zulu_site.id],
        )

    def test_no_context_unchanged(self):
        """AC 6"""
        self._order(self.mary, self.zulu_site)
        self.assertEqual(
            self._suggest(self.sites),
            [self.acme_site_a.id, self.acme_site_b.id, self.globex_site.id, self.zulu_site.id],
        )
        self.assertEqual(
            self.env["res.partner"].search([("id", "in", self.sites.ids)]).ids,
            self._suggest(self.sites),
        )

    def test_form_passes_context(self):
        """AC 7"""
        order_fields = self.env["sale.order"].fields_get(list(self._slots()), ["context"])
        for slot in self._slots():
            self.assertEqual(order_fields[slot]["context"].get("sale_usage_rank"), slot)
        # The address slots rank by the order's customer contact, which the
        # form passes as default_parent_id. They show only to this group.
        self.env.user.group_ids |= self.env.ref("account.group_delivery_invoice_address")
        arch = etree.fromstring(self.env["sale.order"].get_view(view_type="form")["arch"])
        for slot in ("partner_shipping_id", "partner_invoice_id"):
            node = arch.xpath(f"//field[@name='{slot}'][@context]")[0]
            ctx = safe_eval(node.get("context"), {"partner_id": self.jason.id})
            self.assertEqual(ctx.get("default_parent_id"), self.jason.id, slot)

    @staticmethod
    def _slots():
        return ("partner_id", "partner_shipping_id", "partner_invoice_id")
