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
from odoo.tests import Form, tagged

from .common import SalePartnerUsageRankCase


@tagged("post_install", "-at_install")
class TestAddressDefaults(SalePartnerUsageRankCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The form shows the address fields to this group only.
        cls.env.user.group_ids |= cls.env.ref("account.group_delivery_invoice_address")
        Partner = cls.env["res.partner"]
        cls.bob = Partner.create({"name": "Bob New", "parent_id": cls.acme.id})
        cls.gina = Partner.create({"name": "Gina Fresh", "parent_id": cls.globex.id})

    def _defaults(self, contact):
        """The addresses a new order gets for ``contact``, without saving it."""
        form = Form(self.env["sale.order"])
        form.partner_id = contact
        return form.partner_shipping_id, form.partner_invoice_id

    def test_contact_tier(self):
        """AC 1"""
        for _i in range(3):
            self._order(self.mary, self.acme_site_a)
        self._order(self.jason, self.acme_site_b)
        self.assertEqual(self._defaults(self.jason)[0], self.acme_site_b)
        # A drop-ship site under another company counts too.
        self._order(self.jason, self.globex_site)
        self._order(self.jason, self.globex_site)
        self.assertEqual(self._defaults(self.jason)[0], self.globex_site)

    def test_company_tier(self):
        """AC 2"""
        # Odoo's standard choice for Bob would be Site A.
        for _i in range(3):
            self._order(self.mary, self.acme_site_b)
        self._order(self.jason, self.acme_site_a)
        # Heavier use of another company's site does not make it Acme's.
        for _i in range(5):
            self._order(self.mary, self.globex_site)
        self.assertEqual(self._defaults(self.bob)[0], self.acme_site_b)

    def test_core_fallback(self):
        """AC 3"""
        self._order(self.jason, self.acme_site_a, self.acme_billing)
        expected = self.gina.address_get(["delivery", "invoice"])
        shipping, invoice = self._defaults(self.gina)
        self.assertEqual(shipping.id, expected["delivery"])
        self.assertEqual(invoice.id, expected["invoice"])

    def test_invoice_address(self):
        """AC 4"""
        for _i in range(3):
            self._order(self.mary, invoice=self.acme)
        self._order(self.jason, invoice=self.acme_billing)
        self.assertEqual(self._defaults(self.jason)[1], self.acme_billing)
        self.assertEqual(self._defaults(self.bob)[1], self.acme)

    def test_tie_most_recent(self):
        """AC 5"""
        self._order(self.jason, self.acme_site_a)
        self._order(self.jason, self.acme_site_b)
        self.assertEqual(self._defaults(self.jason)[0], self.acme_site_b)
        self.assertEqual(self._defaults(self.bob)[0], self.acme_site_b)
        # More uses beat recency; Mary's order does not touch Jason's tie.
        self._order(self.mary, self.acme_site_a)
        self.assertEqual(self._defaults(self.bob)[0], self.acme_site_a)
        self.assertEqual(self._defaults(self.jason)[0], self.acme_site_b)

    def test_contact_change_reapplies(self):
        """AC 6"""
        self._order(self.jason, self.acme_site_b, self.acme)
        self._order(self.mary, self.acme_site_a, self.acme_billing)
        with Form(self.env["sale.order"]) as form:
            form.partner_id = self.jason
            self.assertEqual(form.partner_shipping_id, self.acme_site_b)
            form.partner_id = self.mary
            self.assertEqual(form.partner_shipping_id, self.acme_site_a)
            self.assertEqual(form.partner_invoice_id, self.acme_billing)

    def test_manual_pick_kept(self):
        """AC 7"""
        self._order(self.jason, self.acme_site_b)
        with Form(self.env["sale.order"]) as form:
            form.partner_id = self.jason
            form.partner_shipping_id = self.acme_site_a
            form.note = "call ahead"
        order = form.record
        self.assertEqual(order.partner_shipping_id, self.acme_site_a)
        with Form(order) as form:
            form.client_order_ref = "PO-1"
        self.assertEqual(order.partner_shipping_id, self.acme_site_a)

    def test_archived_never_default(self):
        """AC 8"""
        site_c = self.env["res.partner"].create({
            "name": "Site C", "type": "delivery", "parent_id": self.acme.id,
        })
        self._order(self.mary, site_c)
        self._order(self.jason, self.acme_site_b)
        self._order(self.jason, self.acme_site_b)
        self.acme_site_b.action_archive()
        # Not Site B (archived), and not Odoo's standard Site A.
        self.assertEqual(self._defaults(self.jason)[0], site_c)
