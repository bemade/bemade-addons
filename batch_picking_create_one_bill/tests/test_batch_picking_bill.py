# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, ValidationError
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

        # Create a batch picking with the pickings
        cls.batch = cls.env["stock.picking.batch"].create(
            {
                "name": "Test Batch",
                "company_id": cls.env.company.id,
                "scheduled_date": fields.Date.today(),
                "picking_ids": [(6, 0, (cls.po1 + cls.po2).picking_ids.ids)],
                "zero_quantity_default": False,
            }
        )

        # Create a batch with multiple vendors for testing validation
        cls.vendor2 = cls.env["res.partner"].create(
            {
                "name": "Second Vendor",
                "email": "vendor2@test.com",
                "supplier_rank": 1,
            }
        )

        # Create a purchase order with a different vendor
        po_vals_vendor2 = {
            "partner_id": cls.vendor2.id,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": cls.product_a.id,
                        "name": cls.product_a.name,
                        "product_qty": 2.0,
                        "product_uom": cls.product_a.uom_po_id.id,
                        "price_unit": 100.0,
                    },
                ),
            ],
        }
        cls.po3 = cls.env["purchase.order"].create(po_vals_vendor2)
        cls.po3.button_confirm()

        # Process the picking for the second vendor
        for picking in cls.po3.picking_ids:
            for move in picking.move_ids:
                move.quantity = move.product_qty

        # Create a batch with multiple vendors
        cls.multi_vendor_batch = cls.env["stock.picking.batch"].create(
            {
                "name": "Multi Vendor Batch",
                "company_id": cls.env.company.id,
                "scheduled_date": fields.Date.today(),
                "picking_ids": [(6, 0, (cls.po1 + cls.po3).picking_ids.ids)],
                "zero_quantity_default": False,
            }
        )

    def test_action_create_bill_success(self):
        """Test that a bill is successfully created from a batch picking"""
        # Ensure the batch has no invoices initially
        self.assertEqual(len(self.batch.invoice_ids), 0)
        self.assertEqual(self.batch.invoice_count, 0)

        # Execute the action to create a bill
        action = self.batch.action_create_bill()

        # Verify that an invoice was created
        self.assertEqual(len(self.batch.invoice_ids), 1)
        self.assertEqual(self.batch.invoice_count, 1)

        # Verify the action returns the correct view
        self.assertEqual(action.get("res_id"), self.batch.invoice_ids[-1].id)
        self.assertEqual(action.get("views")[0][1], "form")

        # Verify the bill content
        bill = self.batch.invoice_ids[-1]
        self.assertEqual(bill.partner_id, self.vendor)
        self.assertEqual(bill.move_type, "in_invoice")
        self.assertEqual(bill.invoice_date, self.batch.scheduled_date.date())

        # Verify that the bill contains the correct lines
        expected_products = self.batch.move_line_ids.mapped("product_id")
        bill_products = bill.invoice_line_ids.mapped("product_id")
        self.assertEqual(set(bill_products.ids), set(expected_products.ids))

        # Verify the quantities match
        for line in bill.invoice_line_ids:
            # Find matching move lines
            move_lines = self.batch.move_line_ids.filtered(
                lambda ml: ml.product_id == line.product_id
            )
            self.assertEqual(line.quantity, sum(move_lines.mapped("quantity")))

            # Verify price from purchase order line
            purchase_line = move_lines[0].move_id.purchase_line_id
            self.assertEqual(line.price_unit, purchase_line.price_unit)

    def test_action_create_bill_no_purchase_orders(self):
        """Test that an error is raised when there are no purchase orders"""
        # Create an empty batch
        empty_batch = self.env["stock.picking.batch"].create(
            {
                "name": "Empty Batch",
                "company_id": self.env.company.id,
                "scheduled_date": fields.Date.today(),
            }
        )

        # Try to create a bill and expect a ValidationError
        with self.assertRaises(ValidationError):
            empty_batch.action_create_bill()

    def test_action_create_bill_multiple_vendors(self):
        """Test that an error is raised when there are multiple vendors"""
        # Try to create a bill from a batch with multiple vendors
        with self.assertRaises(ValidationError):
            self.multi_vendor_batch.action_create_bill()

    def test_action_create_bill_access_rights(self):
        """Test access rights for creating bills from batch pickings"""
        # Test with warehouse user (should have access)
        self.batch.with_user(self.warehouse_user).action_create_bill()

        # Verify that a bill was created
        self.assertEqual(len(self.batch.invoice_ids), 1)

        # Create a user without invoice creation rights
        no_invoice_user = self.env["res.users"].create(
            {
                "name": "No Invoice User",
                "login": "no_invoice_user",
                "email": "no_invoice@test.com",
                "groups_id": [(6, 0, [self.env.ref("stock.group_stock_user").id])],
            }
        )

        # Create a new batch for testing with the limited user
        new_batch = self.env["stock.picking.batch"].create(
            {
                "name": "New Test Batch",
                "company_id": self.env.company.id,
                "scheduled_date": fields.Date.today(),
                "picking_ids": [(6, 0, self.po2.picking_ids.ids)],
            }
        )

        # Try to create a bill with a user that doesn't have invoice creation rights
        with self.assertRaises(AccessError):
            new_batch.with_user(no_invoice_user).action_create_bill()

    def test_bill_values_calculation(self):
        """Test the helper methods that calculate bill values"""
        # Test _get_bill_values method
        bill_values = self.batch._get_bill_values()

        self.assertEqual(bill_values["company_id"], self.batch.company_id.id)
        self.assertEqual(bill_values["partner_id"], self.batch.partner_ids.id)
        self.assertEqual(bill_values["move_type"], "in_invoice")
        self.assertEqual(bill_values["invoice_date"], self.batch.scheduled_date)

        # The invoice_origin should contain the purchase order names
        for po_name in self.batch.purchase_order_ids.mapped("name"):
            self.assertIn(po_name, bill_values["invoice_origin"])

        # Test currency consistency
        currency_id = self.batch._get_currency_id()
        self.assertEqual(currency_id, self.batch.purchase_order_ids[0].currency_id.id)
