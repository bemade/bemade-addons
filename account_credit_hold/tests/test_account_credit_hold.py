# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta
from odoo.tests import common, tagged, Form
from odoo.exceptions import UserError


@tagged("post_install", "-at_install")
class TestAccountCreditHold(common.TransactionCase):

    def setUp(self):
        super().setUp()

        # Create test partner
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "is_company": True,
                "customer_rank": 1,
                "email": "test@example.com",
            }
        )

        # Try to find existing followup lines or create new ones with unique delays
        self.followup_line = self.env["account_followup.followup.line"].search(
            [("delay", "=", 15), ("company_id", "=", self.env.company.id)], limit=1
        )

        if not self.followup_line:
            # Find a unique delay value
            existing_delays = (
                self.env["account_followup.followup.line"]
                .search([("company_id", "=", self.env.company.id)])
                .mapped("delay")
            )

            delay = 15
            while delay in existing_delays:
                delay += 1

            self.followup_line = self.env["account_followup.followup.line"].create(
                {
                    "name": "First Reminder",
                    "delay": delay,
                    "account_hold": True,
                    "send_email": True,
                    "company_id": self.env.company.id,
                }
            )
        else:
            # Update existing line to have account_hold
            self.followup_line.account_hold = True

        # Create followup line without credit hold
        self.followup_line_no_hold = self.env["account_followup.followup.line"].search(
            [("delay", "=", 30), ("company_id", "=", self.env.company.id)], limit=1
        )

        if not self.followup_line_no_hold:
            # Find a unique delay value
            existing_delays = (
                self.env["account_followup.followup.line"]
                .search([("company_id", "=", self.env.company.id)])
                .mapped("delay")
            )

            delay = 30
            while delay in existing_delays:
                delay += 1

            self.followup_line_no_hold = self.env[
                "account_followup.followup.line"
            ].create(
                {
                    "name": "Second Reminder",
                    "delay": delay,
                    "account_hold": False,
                    "send_email": True,
                    "company_id": self.env.company.id,
                }
            )
        else:
            # Update existing line to not have account_hold
            self.followup_line_no_hold.account_hold = False

    def test_credit_hold_basic_functionality(self):
        """Test basic credit hold functionality"""
        # Initially partner should not be on hold
        self.assertFalse(self.partner.on_hold)
        self.assertFalse(self.partner.hold_bg)

        # Place partner on credit hold
        with Form(self.partner) as form:
            form.record.action_credit_hold()
        self.assertTrue(self.partner.hold_bg)
        self.assertTrue(self.partner.on_hold)

        # Lift credit hold
        with Form(self.partner) as form:
            form.record.action_lift_credit_hold()
        self.assertFalse(self.partner.hold_bg)
        self.assertFalse(self.partner.on_hold)

    def test_postpone_hold_functionality(self):
        """Test postpone hold until functionality"""
        # Place partner on hold
        with Form(self.partner) as form:
            form.record.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Set postpone date to tomorrow
        tomorrow = date.today() + timedelta(days=1)
        self.partner.postpone_hold_until = tomorrow

        # Partner should not be on hold due to postponement
        self.assertFalse(self.partner.on_hold)

        # Set postpone date to yesterday
        yesterday = date.today() - timedelta(days=1)
        self.partner.postpone_hold_until = yesterday

        # Partner should be on hold again
        self.assertTrue(self.partner.on_hold)

    def test_commercial_partner_hold_inheritance(self):
        """Test that child contacts inherit hold status from commercial partner"""
        # Create child contact
        child_partner = self.env["res.partner"].create(
            {
                "name": "Child Contact",
                "parent_id": self.partner.id,
                "type": "contact",
            }
        )

        # Place parent on hold
        with Form(self.partner) as form:
            form.record.action_credit_hold()

        # Child should also be on hold
        self.assertTrue(child_partner.on_hold)

        # Lift hold from parent
        self.partner.action_lift_credit_hold()

        # Child should no longer be on hold
        self.assertFalse(child_partner.on_hold)

    def test_sale_order_blocking(self):
        """Test that sale orders are blocked when customer is on credit hold"""
        # Get or create a product for testing
        product = self.env["product.product"].search([("type", "=", "consu")], limit=1)
        if not product:
            product = self.env["product.product"].create(
                {
                    "name": "Test Product",
                    "type": "consu",
                    "list_price": 100.0,
                }
            )

        # Create a sale order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Should be able to confirm when not on hold
        sale_order.action_confirm()
        self.assertEqual(sale_order.state, "sale")

        # Create another order and place customer on hold
        sale_order2 = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        with Form(self.partner) as form:
            form.record.action_credit_hold()

        # Should raise error when trying to confirm
        with self.assertRaises(UserError):
            sale_order2.action_confirm()

    def test_followup_integration(self):
        """Test integration with followup system"""
        # Set partner to in_need_of_action status and assign followup line
        self.partner.write(
            {
                "followup_status": "in_need_of_action",
                "followup_line_id": self.followup_line.id,
            }
        )

        # Execute followup - should place on hold
        self.partner._execute_followup_partner()
        self.assertTrue(self.partner.hold_bg)

        # Test with followup line that doesn't have account_hold
        self.partner.write(
            {
                "followup_line_id": self.followup_line_no_hold.id,
                "hold_bg": False,  # Reset hold status
            }
        )

        # Execute followup - should not place on hold
        self.partner._execute_followup_partner()
        self.assertFalse(self.partner.hold_bg)

    def test_followup_report_options(self):
        """Test that followup report includes credit hold information"""
        # Set up partner with followup line
        self.partner.write(
            {
                "followup_line_id": self.followup_line.id,
            }
        )
        self.partner.action_credit_hold()

        # Get followup report options
        report = self.env["account.followup.report"]
        options = report._get_followup_report_options(self.partner)

        # Should include credit hold information
        self.assertTrue(options.get("credit_hold"))
        self.assertTrue(options.get("partner_on_hold"))

    def test_cleanup_expired_hold_postponements(self):
        """Test automatic cleanup of expired hold postponements"""
        # Set expired postponement date
        expired_date = date.today() - timedelta(days=5)
        self.partner.postpone_hold_until = expired_date

        # Run cleanup
        self.env["res.partner"]._cleanup_expired_hold_postponements()

        # Postponement should be cleared
        self.assertFalse(self.partner.postpone_hold_until)

    def test_hold_bg_computation(self):
        """Test hold_bg field computation based on followup status"""
        # Test with no_action_needed status
        self.partner.write(
            {
                "followup_status": "no_action_needed",
                "followup_line_id": False,
            }
        )
        self.partner._compute_hold_bg()
        self.assertFalse(self.partner.hold_bg)

        # Test with followup status and line
        self.partner.write(
            {
                "followup_status": "in_need_of_action",
                "followup_line_id": self.followup_line.id,
                "hold_bg": True,  # Set initial state
            }
        )
        self.partner._compute_hold_bg()
        # Should preserve existing hold_bg value when there's a followup line
        self.assertTrue(self.partner.hold_bg)

    def test_stock_picking_credit_hold_display(self):
        """Test that stock pickings show credit hold status"""
        # Get warehouse and its outgoing picking type
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        picking_type = warehouse.out_type_id

        # Create a stock picking
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
        )

        # Initially should not show as on hold
        self.assertFalse(picking.client_on_hold)

        # Place partner on hold
        with Form(self.partner) as form:
            form.record.action_credit_hold()

        # Picking should now show as on hold
        self.assertTrue(picking.client_on_hold)

    def test_get_first_followup_level(self):
        """Test _get_first_followup_level method"""
        first_level = self.partner._get_first_followup_level()
        self.assertEqual(first_level, self.followup_line)

        # Create an earlier followup level with unique delay
        existing_delays = (
            self.env["account_followup.followup.line"]
            .search([("company_id", "=", self.env.company.id)])
            .mapped("delay")
        )

        delay = 5
        while delay in existing_delays:
            delay += 1

        earlier_line = self.env["account_followup.followup.line"].create(
            {
                "name": "Early Reminder",
                "delay": delay,
                "account_hold": False,
                "company_id": self.env.company.id,
            }
        )

        first_level = self.partner._get_first_followup_level()
        self.assertEqual(first_level, earlier_line)
