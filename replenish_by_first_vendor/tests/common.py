from odoo.tests import TransactionCase


class ReplenishVendorCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.vendor1 = Partner.create({"name": "Alpha Pneumatics", "supplier_rank": 1})
        cls.vendor2 = Partner.create({"name": "Beta Valves", "supplier_rank": 1})
        cls.product = cls.env["product.product"].create(
            {"name": "Cylinder", "is_storable": True}
        )
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )

    @classmethod
    def _add_price(cls, partner, product=None, **vals):
        product = product or cls.product
        return cls.env["product.supplierinfo"].create(
            {
                "partner_id": partner.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "price": 10.0,
                **vals,
            }
        )

    def _make_line(self, product=None, trigger="manual", **vals):
        return self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": (product or self.product).id,
                "location_id": self.warehouse.lot_stock_id.id,
                "warehouse_id": self.warehouse.id,
                "trigger": trigger,
                **vals,
            }
        )
