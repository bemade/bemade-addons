"""Shared fixtures for MyCarrier delivery tests.

Provides a ``TransactionCase`` subclass with a configured ``delivery.carrier``
of type ``mycarrier``, US origin/destination partners, two LTL-friendly
products with NMFC class set, and helpers to build sale orders and
outgoing pickings ready for rate/ship calls.

Concrete tests mock ``odoo.addons.delivery_mycarrier.models.mycarrier_request.MyCarrierRequest``
rather than hitting MyCarrier hosts.
"""

from odoo.tests import TransactionCase


class MyCarrierCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Product = cls.env["product.product"]

        cls.us = cls.env.ref("base.us")
        cls.state_wa = cls.env.ref("base.state_us_48")
        cls.state_sc = cls.env.ref("base.state_us_41")

        cls.origin_partner = cls.env.ref("base.main_partner")
        cls.origin_partner.write(
            {
                "country_id": cls.us.id,
                "state_id": cls.state_wa.id,
                "city": "Seattle",
                "street": "1 Warehouse Way",
                "zip": "98101",
                "phone": "2065550100",
            }
        )

        cls.destination = Partner.create(
            {
                "name": "Acme Industrial",
                "phone": "8035550199",
                "street": "1515 Main Street",
                "city": "Columbia",
                "state_id": cls.state_sc.id,
                "zip": "29201",
                "country_id": cls.us.id,
            }
        )

        cls.product_pallet_a = Product.create(
            {
                "name": "Steel Brackets (Pallet A)",
                "type": "consu",
                "is_storable": True,
                "weight": 450.0,
                "mycarrier_commodity_class": "70",
            }
        )
        cls.product_pallet_b = Product.create(
            {
                "name": "Foam Insulation (Pallet B)",
                "type": "consu",
                "is_storable": True,
                "weight": 120.0,
                "mycarrier_commodity_class": "125",
            }
        )

        delivery_product = cls.env.ref(
            "delivery_mycarrier.product_product_delivery_mycarrier"
        )
        cls.carrier = cls.env["delivery.carrier"].create(
            {
                "name": "MyCarrier LTL - Seattle",
                "delivery_type": "mycarrier",
                "product_id": delivery_product.id,
                "mycarrier_account_email": "admin@example.com",
                "mycarrier_api_key": "test-api-key",
                "mycarrier_location_id": "LOC-SEA-1",
                "mycarrier_payment_direction": "Prepaid",
                "mycarrier_ready_to_dispatch": True,
                "mycarrier_weight_unit": "LBS",
                "mycarrier_measurement_unit": "IN",
                "mycarrier_default_commodity_class": "70",
                "mycarrier_webhook_token": "test-token",
            }
        )

    def make_picking(self, products=None):
        """Confirm a sale order and return its first outgoing picking."""
        order = self.make_sale_order(products=products)
        order.action_confirm()
        picking = order.picking_ids[:1]
        if not picking:
            self.fail("sale order did not generate a picking")
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.scheduled_date = "2026-05-01"
        return picking

    def make_sale_order(self, products=None):
        """Build a confirmed-but-not-shipped sale order for the given
        products (defaults to one unit of each pallet product)."""
        SaleOrder = self.env["sale.order"]
        if products is None:
            products = [(self.product_pallet_a, 1.0), (self.product_pallet_b, 1.0)]
        order_lines = [
            (
                0,
                0,
                {
                    "product_id": p.id,
                    "name": p.display_name,
                    "product_uom_qty": qty,
                    "price_unit": p.lst_price or 100.0,
                },
            )
            for p, qty in products
        ]
        return SaleOrder.create(
            {
                "partner_id": self.destination.id,
                "carrier_id": self.carrier.id,
                "order_line": order_lines,
            }
        )
