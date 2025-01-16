from odoo.addons.sale_purchase_inter_company_rules.models.purchase_order import (
    purchase_order,
)
from odoo.tests import TransactionCase, tagged, Form
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
                            "price": 3000,
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
                            "price": 5000,
                        },
                    )
                ],
            }
        )

        cls.agreement_1 = cls.env["purchase.requisition"].create(
            {
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

    def test_competing_sale_orders_get_two_lines(self):
        purchase_order = self._generate_2_sales_1_purchase_clients_1_3()
        self.assertEqual(len(purchase_order.order_line), 2)
        self.assertEqual(
            purchase_order.order_line[0].requisition_id,
            self.agreement_1,
            f"PO line for Partner 1 should have requisition {self.agreement_1.name}, not {purchase_order.order_line[0].requisition_id.name}",
        )
        self.assertEqual(
            purchase_order.order_line[1].requisition_id,
            self.agreement_2,
            f"PO line for Partner 2 should have requisition {self.agreement_2.name}, not {purchase_order.order_line[1].requisition_id.name}"
            f"PO line has sale order {purchase_order.order_line[1].sale_order_id} and sale line {purchase_order.order_line[1].sale_line_id}"
            f"PO has sales orders {purchase_order._get_sale_orders()}"
            f"PO has requisition {purchase_order.requisition_id}",
        )

    def _generate_2_sales_1_purchase_clients_1_3(self):
        sale_order_1 = self.env["sale.order"].create(
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
        sale_order_1.action_confirm()
        sale_order_2 = self.env["sale.order"].create(
            {
                "partner_id": self.client_3.id,
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
        sale_order_2.action_confirm()
        purchase_order = sale_order_1._get_purchase_orders()[0]
        return purchase_order

    def test_lines_from_multiple_sales_get_correct_pricing(self):
        purchase_order = self._generate_2_sales_1_purchase_clients_1_3()

        self.assertEqual(purchase_order.order_line[0].price_unit, 1000)
        self.assertEqual(purchase_order.order_line[1].price_unit, 1500)

    def test_removing_line_agreement_recomputes_pricing(self):
        purchase_order = self._generate_2_sales_1_purchase_clients_1_3()
        purchase_order.requisition_id = False

        line = purchase_order.order_line[0]
        line.requisition_id = False

        self.assertEqual(purchase_order.order_line[0].price_unit, 3000)
