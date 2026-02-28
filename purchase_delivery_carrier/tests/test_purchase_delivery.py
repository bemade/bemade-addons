from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("post_install", "-at_install")
class TestPurchaseDelivery(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delivery_product_1 = cls.env["product.product"].create(
            {
                "name": "Local Delivery Product",
                "type": "service",
            }
        )
        delivery_product_2 = cls.env["product.product"].create(
            {
                "name": "Free Delivery Product",
                "type": "service",
            }
        )
        cls.carrier_1 = cls.env["delivery.carrier"].create(
            {
                "name": "Test Local Delivery",
                "delivery_type": "fixed",
                "product_id": delivery_product_1.id,
                "fixed_price": 10.0,
            }
        )
        cls.carrier_2 = cls.env["delivery.carrier"].create(
            {
                "name": "Test Free Delivery",
                "delivery_type": "fixed",
                "product_id": delivery_product_2.id,
                "fixed_price": 0.0,
            }
        )

        cls.partner_1 = cls.env["res.partner"].create(
            {
                "name": "Test 1",
                "purchase_delivery_carrier_id": cls.carrier_1.id,
            }
        )
        cls.partner_2 = cls.env["res.partner"].create(
            {
                "name": "Test 2",
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test product",
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": cls.partner_1.id,
                            "price": 100.0,
                        }
                    ),
                    Command.create(
                        {
                            "partner_id": cls.partner_2.id,
                            "price": 200.0,
                        }
                    ),
                ],
            }
        )

    def test_carrier_set_on_purchase_order_when_default_is_set(self):
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_1.id,
                "order_line": [Command.create({"product_id": self.product.id})],
            }
        )

        self.assertEqual(purchase_order.carrier_id, self.carrier_1)

    def test_carrier_not_set_on_purchase_order_when_default_is_not_set(self):
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_2.id,
            }
        )
        self.assertFalse(purchase_order.carrier_id)

    def test_carrier_trickles_down_to_picking(self):
        purchase_order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_1.id,
                "order_line": [Command.create({"product_id": self.product.id})],
            }
        )
        purchase_order.button_confirm()
        picking = purchase_order.picking_ids
        self.assertEqual(picking.carrier_id, self.carrier_1)
