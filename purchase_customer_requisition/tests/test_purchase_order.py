from odoo.tests import TransactionCase, tagged
from odoo import Command, fields
from datetime import timedelta


@tagged("post_install", "-at_install")
class TestPurchaseOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env.ref("base.res_partner_18")
        cls.client_1 = cls.env.ref("base.res_partner_2")
        cls.client_2 = cls.env.ref("base.res_partner_3")
        cls.client_3 = cls.env.ref("base.res_partner_4")
        cls.product_1 = cls.env.ref("product.product_delivery_01")
        cls.product_2 = cls.env.ref("product.product_delivery_02")

        cls.env["stock.rule"].search(
            [
                ("action", "=", "pull"),
                (
                    "location_dest_id",
                    "=",
                    cls.env.ref("stock.stock_location_customers").id,
                ),
            ]
        ).write({"procure_method": "mts_else_mto"})

        cls.env["product.supplierinfo"].create(
            [
                {
                    "partner_id": cls.supplier.id,
                    "product_id": cls.product_1.id,
                    "price": 2000,
                },
                {
                    "partner_id": cls.supplier.id,
                    "product_id": cls.product_2.id,
                    "price": 3000,
                },
            ]
        )

        cls.agreement_1 = cls.env["purchase.requisition"].create(
            {
                "name": "ATRACK 123",
                "vendor_id": 1,
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
                "vendor_id": 1,
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

        purchase_line = sale_order.order_line[0].purchase_line_ids
        self.assertEqual(purchase_line.requisition_id, self.agreement_1)
