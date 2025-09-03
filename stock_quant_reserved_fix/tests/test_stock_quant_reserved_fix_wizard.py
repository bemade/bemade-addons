from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError
from odoo import fields


class TestStockQuantReservedFixWizard(TransactionCase):

    def setUp(self):
        super().setUp()

        # Create test data
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "product",
                "tracking": "none",
            }
        )

        self.location = self.env["stock.location"].create(
            {
                "name": "Test Location",
                "usage": "internal",
            }
        )

        # Create stock quants for testing
        self.quant1 = self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.location.id,
                "quantity": 100.0,
                "reserved_quantity": 10.0,
            }
        )

        self.quant2 = self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.location.id,
                "quantity": 50.0,
                "reserved_quantity": 5.0,
            }
        )

        # Create stock manager user for testing
        self.stock_manager = self.env["res.users"].create(
            {
                "name": "Test Stock Manager",
                "login": "test_stock_manager",
                "email": "test@example.com",
                "groups_id": [(6, 0, [self.env.ref("stock.group_stock_manager").id])],
            }
        )

        # Create regular user without stock manager rights
        self.regular_user = self.env["res.users"].create(
            {
                "name": "Test Regular User",
                "login": "test_regular_user",
                "email": "regular@example.com",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def test_wizard_default_get_single_quant(self):
        """Test wizard default_get with single quant"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_context(active_ids=[self.quant1.id], active_model="stock.quant")
            .create({})
        )

        self.assertEqual(len(wizard.quant_ids), 1)
        self.assertEqual(wizard.quant_ids[0], self.quant1)
        self.assertEqual(wizard.quant_count, 1)

    def test_wizard_default_get_multiple_quants(self):
        """Test wizard default_get with multiple quants"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_context(
                active_ids=[self.quant1.id, self.quant2.id], active_model="stock.quant"
            )
            .create({})
        )

        self.assertEqual(len(wizard.quant_ids), 2)
        self.assertIn(self.quant1, wizard.quant_ids)
        self.assertIn(self.quant2, wizard.quant_ids)
        self.assertEqual(wizard.quant_count, 2)

    def test_successful_reserved_quantity_update(self):
        """Test successful update of reserved quantity"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id])],
                    "reserved_quantity": 20.0,
                }
            )
        )

        # Execute the action
        result = wizard.action_fix_reserved_quantity()

        # Check that reserved quantity was updated
        self.assertEqual(self.quant1.reserved_quantity, 20.0)

        # Check that success notification is returned
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_multiple_quants_update(self):
        """Test updating multiple quants at once"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id, self.quant2.id])],
                    "reserved_quantity": 15.0,
                }
            )
        )

        # Execute the action
        wizard.action_fix_reserved_quantity()

        # Check that both quants were updated
        self.assertEqual(self.quant1.reserved_quantity, 15.0)
        self.assertEqual(self.quant2.reserved_quantity, 15.0)

    def test_validation_no_quants_selected(self):
        """Test validation when no quants are selected"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [])],
                    "reserved_quantity": 10.0,
                }
            )
        )

        with self.assertRaises(UserError) as cm:
            wizard.action_fix_reserved_quantity()

        self.assertIn("No stock quants selected", str(cm.exception))

    def test_validation_negative_reserved_quantity(self):
        """Test validation for negative reserved quantity"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id])],
                    "reserved_quantity": -5.0,
                }
            )
        )

        with self.assertRaises(UserError) as cm:
            wizard.action_fix_reserved_quantity()

        self.assertIn("Reserved quantity cannot be negative", str(cm.exception))

    def test_validation_reserved_exceeds_available(self):
        """Test validation when reserved quantity exceeds available quantity"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id])],
                    "reserved_quantity": 150.0,  # More than the 100.0 available
                }
            )
        )

        with self.assertRaises(UserError) as cm:
            wizard.action_fix_reserved_quantity()

        self.assertIn(
            "Reserved quantity (150.00) cannot exceed available quantity (100.00)",
            str(cm.exception),
        )

    def test_security_stock_manager_access(self):
        """Test that stock managers can access the wizard"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id])],
                    "reserved_quantity": 20.0,
                }
            )
        )

        # This should not raise an exception
        result = wizard.action_fix_reserved_quantity()
        self.assertEqual(result["type"], "ir.actions.client")

    def test_security_regular_user_denied(self):
        """Test that regular users cannot perform the action"""
        with self.assertRaises(AccessError):
            wizard = (
                self.env["stock.quant.reserved.fix.wizard"]
                .with_user(self.regular_user)
                .create(
                    {
                        "quant_ids": [(6, 0, [self.quant1.id])],
                        "reserved_quantity": 20.0,
                    }
                )
            )
            wizard.action_fix_reserved_quantity()

    def test_zero_reserved_quantity(self):
        """Test setting reserved quantity to zero"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id])],
                    "reserved_quantity": 0.0,
                }
            )
        )

        wizard.action_fix_reserved_quantity()
        self.assertEqual(self.quant1.reserved_quantity, 0.0)

    def test_reserved_quantity_equals_available(self):
        """Test setting reserved quantity equal to available quantity"""
        wizard = (
            self.env["stock.quant.reserved.fix.wizard"]
            .with_user(self.stock_manager)
            .create(
                {
                    "quant_ids": [(6, 0, [self.quant1.id])],
                    "reserved_quantity": 100.0,  # Equal to available quantity
                }
            )
        )

        wizard.action_fix_reserved_quantity()
        self.assertEqual(self.quant1.reserved_quantity, 100.0)

    def test_quant_count_computation(self):
        """Test quant_count field computation"""
        wizard = self.env["stock.quant.reserved.fix.wizard"].create(
            {
                "quant_ids": [(6, 0, [self.quant1.id, self.quant2.id])],
                "reserved_quantity": 0,
            }
        )

        self.assertEqual(wizard.quant_count, 2)

        # Remove one quant
        wizard.quant_ids = [(6, 0, [self.quant1.id])]
        self.assertEqual(wizard.quant_count, 1)

        # Remove all quants
        wizard.quant_ids = [(6, 0, [])]
        self.assertEqual(wizard.quant_count, 0)
