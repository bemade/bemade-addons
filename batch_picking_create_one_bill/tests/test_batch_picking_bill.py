# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError
from odoo import fields


@tagged("post_install", "-at_install")
class TestBatchPickingBill(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create users with different access rights
        cls.warehouse_user = cls.env["res.users"].create(
            {
                "name": "Warehouse User",
                "login": "warehouse_user",
                "email": "warehouse@test.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("stock.group_stock_user").id,
                            cls.env.ref("purchase.group_purchase_user").id,
                            cls.env.ref(
                                "account.group_account_invoice"
                            ).id,  # Basic invoice rights
                        ],
                    )
                ],
            }
        )
        cls.accountant = cls.env["res.users"].create(
            {
                "name": "Accountant",
                "login": "accountant",
                "email": "accountant@test.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("account.group_account_invoice").id,
                            cls.env.ref("account.group_account_manager").id,
                        ],
                    )
                ],
            }
        )

        # Create vendor
        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Test Vendor",
                "email": "vendor@test.com",
                "supplier_rank": 1,
            }
        )

        # Create products
        cls.product_a = cls.env["product.product"].create(
            {
                "name": "Product A",
                "type": "consu",
                "tracking": "none",
                "purchase_ok": True,
            }
        )
        cls.product_b = cls.env["product.product"].create(
            {
                "name": "Product B",
                "type": "consu",
                "tracking": "none",
                "purchase_ok": True,
            }
        )

        # Create purchase orders
        po_vals = {
            "partner_id": cls.vendor.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": cls.product_a.id,
                        "name": cls.product_a.name,
                        "product_qty": 5.0,
                        "product_uom": cls.product_a.uom_po_id.id,
                        "price_unit": 100.0,
                    },
                ),
                (
                    0,
                    0,
                    {
                        "product_id": cls.product_b.id,
                        "name": cls.product_b.name,
                        "product_qty": 3.0,
                        "product_uom": cls.product_b.uom_po_id.id,
                        "price_unit": 200.0,
                    },
                ),
            ],
        }
        cls.po1 = cls.env["purchase.order"].create(po_vals)
        cls.po2 = cls.env["purchase.order"].create(po_vals)

        # Confirm purchase orders and receive products
        cls.po1.button_confirm()
        cls.po2.button_confirm()

        # Receive products in pickings
        for picking in (cls.po1 + cls.po2).picking_ids:
            for move in picking.move_ids:
                move.quantity = move.product_qty

    def test_01_warehouse_user_flow(self):
        """Test the complete flow with warehouse user"""
        # Switch to warehouse user
        self.env = self.env(user=self.warehouse_user)

        # Create batch picking
        batch = self.env["stock.picking.batch"].create(
            {
                "picking_ids": [
                    (6, 0, (self.po1.picking_ids + self.po2.picking_ids).ids)
                ],
                "zero_quantity_default": True,
            }
        )

        # Check batch was created successfully
        self.assertTrue(batch, "Batch picking should be created")
        self.assertEqual(len(batch.picking_ids), 2, "Batch should have 2 pickings")

        # Process the pickings
        for picking in batch.picking_ids:
            for move_line in picking.move_line_ids:
                move_line.quantity = move_line.move_id.product_qty

        # Validate batch
        batch.action_done()
        self.assertEqual(batch.state, "done", "Batch should be done")

        # Try to create bill (should work)
        wizard = (
            self.env["create.bill.wizard"]
            .with_context(default_batch_id=batch.id)
            .create({})
        )

        # Execute the create bill action
        action = wizard.action_create_bill()
        self.assertTrue(action, "Should get action to merge bills")
        self.assertEqual(
            action["res_model"], "merge.bill.wizard", "Should open merge bill wizard"
        )

    def test_02_bill_creation_and_access(self):
        """Test bill creation and access rights"""
        # Create and process batch as warehouse user
        self.env = self.env(user=self.warehouse_user)

        batch = self.env["stock.picking.batch"].create(
            {
                "picking_ids": [
                    (6, 0, (self.po1.picking_ids + self.po2.picking_ids).ids)
                ],
                "zero_quantity_default": True,
            }
        )

        # Process pickings as warehouse user
        for picking in batch.picking_ids:
            for move_line in picking.move_line_ids:
                move_line.quantity = move_line.move_id.product_qty
        batch.action_done()

        # Create bill as warehouse user
        wizard = (
            self.env["create.bill.wizard"]
            .with_context(default_batch_id=batch.id)
            .create({})
        )
        action = wizard.action_create_bill()

        # Execute merge wizard as warehouse user
        merge_wizard = (
            self.env["merge.bill.wizard"].with_context(**action["context"]).create({})
        )

        draft_invoices = merge_wizard.invoice_ids
        self.assertTrue(draft_invoices, "Invoices should be created")

        bill = self.env["account.move"].browse(merge_wizard.action_process()["res_id"])
        self.assertTrue(bill, "Bill should be created")
        self.assertEqual(
            bill.mapped("state"),
            ["draft"],
            "Bill should be draft",
        )

        # Validate invoice as accountant (should work)
        bill.with_user(self.accountant).invoice_date = fields.Date.today()
        bill.with_user(self.accountant).action_post()
        self.assertEqual(
            bill.mapped("state"),
            ["posted"],
            "Bill should be posted",
        )

    def test_03_multi_vendor_constraint(self):
        """Test constraint preventing batch with multiple vendors"""
        # Create another vendor and PO
        other_vendor = self.env["res.partner"].create(
            {
                "name": "Other Vendor",
                "email": "other@test.com",
                "supplier_rank": 1,
            }
        )

        other_po = self.env["purchase.order"].create(
            {
                "partner_id": other_vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "product_qty": 1,
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        other_po.button_confirm()

        # Try to create batch with multiple vendors (should fail)
        with self.assertRaises(Exception):
            self.env["stock.picking.batch"].create(
                {
                    "picking_ids": [
                        (6, 0, (self.po1.picking_ids + other_po.picking_ids).ids)
                    ],
                }
            )
