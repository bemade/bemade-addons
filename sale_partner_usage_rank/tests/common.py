# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo.tests import TransactionCase


class SalePartnerUsageRankCase(TransactionCase):
    """Two customer companies, each with people and addresses."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.acme = Partner.create({"name": "Acme Corp", "is_company": True})
        cls.jason = Partner.create({"name": "Jason Smith", "parent_id": cls.acme.id})
        cls.mary = Partner.create({"name": "Mary Jones", "parent_id": cls.acme.id})
        cls.acme_site_a = Partner.create({
            "name": "Site A", "type": "delivery", "parent_id": cls.acme.id,
        })
        cls.acme_site_b = Partner.create({
            "name": "Site B", "type": "delivery", "parent_id": cls.acme.id,
        })
        cls.acme_billing = Partner.create({
            "name": "Accounts Payable", "type": "invoice", "parent_id": cls.acme.id,
        })
        cls.globex = Partner.create({"name": "Globex", "is_company": True})
        cls.globex_site = Partner.create({
            "name": "Globex Site", "type": "delivery", "parent_id": cls.globex.id,
        })

    @classmethod
    def _order(cls, contact, shipping=None, invoice=None, **vals):
        """A quotation with exactly these partners in the three slots."""
        return cls.env["sale.order"].create({
            "partner_id": contact.id,
            "partner_shipping_id": (shipping or contact).id,
            "partner_invoice_id": (invoice or contact).id,
            **vals,
        })

    def assertRanks(self, partner, contact, shipping, invoice):
        partner.invalidate_recordset()
        self.assertEqual(
            (partner.sale_contact_rank, partner.sale_shipping_rank, partner.sale_invoice_rank),
            (contact, shipping, invoice),
            f"ranks (contact, shipping, invoice) of {partner.name}",
        )
