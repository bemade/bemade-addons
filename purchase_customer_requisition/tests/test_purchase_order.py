from odoo.tests import TransactionCase, tagged
from odoo import Command, fields
from datetime import timedelta


@tagged("post_install", "-at_install")
class TestPurchaseOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.buy_route = cls.env.ref("purchase_stock.route_warehouse0_buy")
        cls.mto_route.active = True
        cls.supplier = cls.env.ref("base.res_partner_18")
        cls.client_1 = cls.env.ref("base.res_partner_2")
        cls.client_2 = cls.env.ref("base.res_partner_3")
        cls.client_3 = cls.env.ref("base.res_partner_4")
        cls.product_1 = cls.env["product.product"].create(
            {
                "name": "SuperProduct",
                "is_storable": True,
                "route_ids": [Command.set((cls.mto_route + cls.buy_route).ids)],
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": cls.supplier.id,
                            "price": 1000,
                        },
                    )
                ],
            }
        )

        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "SuperProduct2",
                "is_storable": True,
                "route_ids": [Command.set((cls.mto_route + cls.buy_route).ids)],
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": cls.supplier.id,
                            "price": 2000,
                        },
                    )
                ],
            }
        )

        cls.agreement_1 = cls.env["purchase.requisition"].create(
            {
                "name": "ATRACK 123",
                "vendor_id": cls.supplier.id,
                "customer_ids": [Command.set([cls.client_1.id, cls.client_2.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": cls.product_1.id,
                            "product_qty": 100,
                            "price_unit": 1000,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": cls.product_2.id,
                            "product_qty": 100,
                            "price_unit": 2000,
                        }
                    ),
                ],
                "date_start": fields.Date.today() - timedelta(days=100),
                "date_end": fields.Date.today() + timedelta(days=265),
            }
        )
        cls.agreement_1.action_confirm()
        cls.agreement_2 = cls.env["purchase.requisition"].create(
            {
                "name": "ATRACK 456",
                "vendor_id": cls.supplier.id,
                "customer_ids": [Command.set([cls.client_3.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": cls.product_1.id,
                            "product_qty": 100,
                            "price_unit": 1500,
                        }
                    ),
                ],
                "date_start": fields.Date.today() - timedelta(days=100),
                "date_end": fields.Date.today() + timedelta(days=265),
            }
        )
        cls.agreement_1.action_confirm()

    def test_one_purchase_order_line_gets_correct_agreement(self):
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.client_1.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_uom_qty": 50,
                        }
                    )
                ],
            }
        )
        sale_order.action_confirm()

        self.assertTrue(sale_order._get_purchase_orders())
        purchase_line = sale_order._get_purchase_orders()[0].order_line[0]
        self.assertEqual(purchase_line.order_id.partner_id, self.supplier)
        self.assertEqual(purchase_line.requisition_id, self.agreement_1)
