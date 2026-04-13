from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError


class TestInventoryAdjustmentSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test product
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "is_storable": True,
            }
        )

        # Get stock location
        cls.stock_location = cls.env.ref("stock.warehouse0").lot_stock_id

        # Create initial quant with some quantity
        cls.quant = (
            cls.env["stock.quant"]
            .sudo()
            .create(
                {
                    "product_id": cls.product.id,
                    "location_id": cls.stock_location.id,
                    "quantity": 100.0,
                }
            )
        )

        # Create test users
        # Regular inventory user (can count but not apply)
        cls.inventory_user = cls.env["res.users"].create(
            {
                "name": "Inventory Counter",
                "login": "inventory_counter",
                "email": "counter@test.com",
                "groups_id": [(6, 0, [cls.env.ref("stock.group_stock_user").id])],
            }
        )

        # Privileged user (can count and apply)
        cls.privileged_user = cls.env["res.users"].create(
            {
                "name": "Inventory Manager",
                "login": "inventory_manager",
                "email": "manager@test.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("stock.group_stock_user").id,
                            cls.env.ref(
                                "stock_inventory_adjustment_security.group_inventory_manual_adjustments"
                            ).id,
                        ],
                    )
                ],
            }
        )

    def test_regular_user_can_set_inventory_quantity(self):
        """Test that regular users can set inventory_quantity (count)"""
        quant = self.quant.with_user(self.inventory_user).with_context(
            inventory_mode=True
        )

        # Should be able to set inventory_quantity
        quant.write({"inventory_quantity": 90.0})
        self.assertEqual(quant.inventory_quantity, 90.0)
        self.assertEqual(quant.inventory_diff_quantity, -10.0)

    def test_regular_user_cannot_apply_adjustment(self):
        """Test that regular users cannot apply adjustments (modify quantity)"""
        quant = self.quant.with_user(self.inventory_user).with_context(inventory_mode=True)

        # Set inventory quantity first
        quant.write({"inventory_quantity": 90.0})

        # Trying to apply (which writes to quantity field) should fail
        with self.assertRaises(AccessError):
            quant.write({"quantity": 90.0})

    def test_regular_user_cannot_create_quants_in_inventory_mode(self):
        """Test that regular users cannot create new quants in inventory mode"""
        # Create a new product
        new_product = self.env["product.product"].create(
            {
                "name": "New Product",
                "type": "consu",
                "is_storable": True,
            }
        )

        # Trying to create a quant in inventory mode should fail
        with self.assertRaises(AccessError):
            self.env["stock.quant"].with_user(self.inventory_user).with_context(
                inventory_mode=True
            ).create(
                {
                    "product_id": new_product.id,
                    "location_id": self.stock_location.id,
                    "quantity": 50.0,
                }
            )

    def test_regular_user_cannot_call_apply_inventory(self):
        """Test that regular users cannot call action_apply_inventory"""
        quant = self.quant.with_user(self.inventory_user).with_context(
            inventory_mode=True
        )

        # Set inventory quantity
        quant.write({"inventory_quantity": 90.0})

        # Trying to apply inventory should fail
        with self.assertRaises(AccessError):
            quant.action_apply_inventory()

    def test_privileged_user_can_apply_adjustment(self):
        """Test that privileged users can apply adjustments"""
        quant = self.quant.with_user(self.privileged_user).with_context(
            inventory_mode=True
        )

        # Set inventory quantity
        quant.write({"inventory_quantity": 90.0})

        # Should be able to apply the adjustment
        quant.action_apply_inventory()

        # Quantity should be updated
        self.assertEqual(quant.quantity, 90.0)
        self.assertEqual(quant.inventory_quantity_set, False)

    def test_privileged_user_can_create_quants_in_inventory_mode(self):
        """Test that privileged users can create new quants in inventory mode"""
        # Create a new product
        new_product = self.env["product.product"].create(
            {
                "name": "Privileged Product",
                "type": "consu",
                "is_storable": True,
            }
        )

        # Privileged user should be able to create a quant in inventory mode
        quant = self.env["stock.quant"].with_user(self.privileged_user).with_context(
            inventory_mode=True
        ).create(
            {
                "product_id": new_product.id,
                "location_id": self.stock_location.id,
                "quantity": 50.0,
            }
        )

        self.assertEqual(quant.quantity, 50.0)
        self.assertEqual(quant.product_id, new_product)

    def test_automatic_operations_not_affected(self):
        """Test that automatic stock operations work normally"""
        # Create a stock move (simulating a picking or manufacturing operation)
        # These operations don't set inventory_mode context
        move = self.env["stock.move"].create(
            {
                "name": "Test Move",
                "product_id": self.product.id,
                "product_uom_qty": 10.0,
                "product_uom": self.product.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.stock_location.id,
            }
        )

        move._action_confirm()
        move._action_assign()
        # Set quantity on the move itself
        move.quantity = 10.0
        move.picked = True
        move._action_done()

        # Quant quantity should be updated automatically
        # Find the quant for this product in stock location
        quant = self.env["stock.quant"].search(
            [
                ("product_id", "=", self.product.id),
                ("location_id", "=", self.stock_location.id),
            ]
        )
        self.assertEqual(quant.quantity, 110.0)

    def test_regular_user_can_view_quantities(self):
        """Test that regular users can view all quantity fields"""
        quant = self.quant.with_user(self.inventory_user)

        # Should be able to read all fields
        self.assertEqual(quant.quantity, 100.0)
        self.assertEqual(quant.inventory_quantity, 0.0)

        # Should be able to read in inventory mode too
        quant_inv_mode = quant.with_context(inventory_mode=True)
        self.assertEqual(quant_inv_mode.quantity, 100.0)

    def test_non_inventory_mode_writes_allowed(self):
        """Test that quantity writes outside inventory mode are not restricted"""
        # Even regular users can write quantity when not in inventory_mode
        # (though they typically wouldn't have access to do this via UI)
        quant = self.quant.sudo()

        # Without inventory_mode context, write should work
        quant.write({"quantity": 95.0})

        self.assertEqual(quant.quantity, 95.0)

    def test_inventory_mode_detection(self):
        """Test that _is_inventory_mode() works correctly"""
        quant = self.quant.with_user(self.inventory_user)

        # Without inventory_mode context
        self.assertFalse(quant._is_inventory_mode())

        # With inventory_mode context
        quant_inv = quant.with_context(inventory_mode=True)
        self.assertTrue(quant_inv._is_inventory_mode())

        # User without stock_user group shouldn't trigger inventory mode
        basic_user = self.env["res.users"].create(
            {
                "name": "Basic User",
                "login": "basic_user",
                "email": "basic@test.com",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        quant_basic = self.quant.with_user(basic_user).with_context(inventory_mode=True)
        self.assertFalse(quant_basic._is_inventory_mode())

    def test_multiple_quants_adjustment(self):
        """Test applying adjustments to multiple quants at once"""
        # Create another product to avoid quant merging
        product2 = self.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "consu",
                "is_storable": True,
            }
        )
        
        # Create another quant with different product
        quant2 = (
            self.env["stock.quant"]
            .sudo()
            .create(
                {
                    "product_id": product2.id,
                    "location_id": self.stock_location.id,
                    "quantity": 50.0,
                }
            )
        )

        # Set inventory quantities on both quants
        self.quant.with_user(self.privileged_user).with_context(
            inventory_mode=True
        ).write({"inventory_quantity": 80.0})
        quant2.with_user(self.privileged_user).with_context(inventory_mode=True).write(
            {"inventory_quantity": 40.0}
        )

        # Apply all at once
        quants = (
            (self.quant | quant2)
            .with_user(self.privileged_user)
            .with_context(inventory_mode=True)
        )
        quants.action_apply_inventory()

        self.assertEqual(self.quant.quantity, 80.0)
        self.assertEqual(quant2.quantity, 40.0)

    def test_regular_user_multiple_quants_blocked(self):
        """Test that regular users cannot apply multiple quants"""
        # Create another product to avoid quant merging
        product2 = self.env["product.product"].create(
            {
                "name": "Test Product 3",
                "type": "consu",
                "is_storable": True,
            }
        )
        
        quant2 = (
            self.env["stock.quant"]
            .sudo()
            .create(
                {
                    "product_id": product2.id,
                    "location_id": self.stock_location.id,
                    "quantity": 50.0,
                }
            )
        )

        # Set inventory quantities
        self.quant.with_user(self.inventory_user).with_context(
            inventory_mode=True
        ).write({"inventory_quantity": 80.0})
        quant2.with_user(self.inventory_user).with_context(inventory_mode=True).write(
            {"inventory_quantity": 40.0}
        )

        # Trying to apply should fail
        quants = (
            (self.quant | quant2)
            .with_user(self.inventory_user)
            .with_context(inventory_mode=True)
        )
        with self.assertRaises(AccessError):
            quants.action_apply_inventory()
