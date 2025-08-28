from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestReplenishByFirstVendor(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test vendors
        cls.vendor1 = cls.env["res.partner"].create(
            {
                "name": "First Vendor",
                "supplier_rank": 1,
            }
        )

        cls.vendor2 = cls.env["res.partner"].create(
            {
                "name": "Second Vendor",
                "supplier_rank": 1,
            }
        )

        # Create test product with Make to Stock route
        cls.product_mts = cls.env["product.product"].create(
            {
                "name": "Test Product MTS",
                "type": "consu",
                "tracking": "none",
                "list_price": 100.0,
                "standard_price": 80.0,
            }
        )

        # Create supplier info for the product (vendor1 first, vendor2 second)
        cls.supplierinfo1 = cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor1.id,
                "product_tmpl_id": cls.product_mts.product_tmpl_id.id,
                "min_qty": 1,
                "price": 75.0,
                "sequence": 1,  # First vendor
            }
        )

        cls.supplierinfo2 = cls.env["product.supplierinfo"].create(
            {
                "partner_id": cls.vendor2.id,
                "product_tmpl_id": cls.product_mts.product_tmpl_id.id,
                "min_qty": 1,
                "price": 70.0,
                "sequence": 2,  # Second vendor
            }
        )

        # Create a product without vendors
        cls.product_no_vendor = cls.env["product.product"].create(
            {
                "name": "Product Without Vendor",
                "type": "consu",
                "tracking": "none",
                "list_price": 50.0,
                "standard_price": 40.0,
            }
        )

        # Get warehouse and location
        cls.warehouse = cls.env["stock.warehouse"].search([], limit=1)
        cls.location = cls.warehouse.lot_stock_id

    def test_manual_orderpoint_sets_first_vendor(self):
        """Test that manual orderpoints automatically set the first vendor."""
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product_mts.id,
                "location_id": self.location.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 5.0,
                "product_max_qty": 20.0,
                "trigger": "manual",
            }
        )

        # Check that supplier_id is set to the first vendor's supplierinfo
        self.assertEqual(
            orderpoint.supplier_id,
            self.supplierinfo1,
            "Manual orderpoint should automatically set the first vendor as supplier_id",
        )

    def test_auto_orderpoint_no_vendor_setting(self):
        """Test that automatic orderpoints don't get auto-vendor setting."""
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product_mts.id,
                "location_id": self.location.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 5.0,
                "product_max_qty": 20.0,
                "trigger": "auto",
            }
        )

        # Check that supplier_id is not set for auto trigger
        self.assertFalse(
            orderpoint.supplier_id,
            "Auto orderpoint should not automatically set supplier_id",
        )

    def test_manual_orderpoint_with_existing_vendor(self):
        """Test that manual orderpoints with existing vendor don't get overridden."""
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product_mts.id,
                "location_id": self.location.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 5.0,
                "product_max_qty": 20.0,
                "trigger": "manual",
                "supplier_id": self.supplierinfo2.id,  # Pre-set to second vendor
            }
        )

        # Check that supplier_id remains the pre-set vendor
        self.assertEqual(
            orderpoint.supplier_id,
            self.supplierinfo2,
            "Manual orderpoint with existing supplier should not be overridden",
        )

    def test_manual_orderpoint_no_vendors_available(self):
        """Test that manual orderpoints for products without vendors don't crash."""
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product_no_vendor.id,
                "location_id": self.location.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 5.0,
                "product_max_qty": 20.0,
                "trigger": "manual",
            }
        )

        # Check that supplier_id remains empty
        self.assertFalse(
            orderpoint.supplier_id,
            "Manual orderpoint for product without vendors should have no supplier_id",
        )

    def test_vendor_sequence_respected(self):
        """Test that the vendor with the lowest sequence is selected."""
        # Update sequences to ensure vendor2 comes first
        self.supplierinfo1.sequence = 10
        self.supplierinfo2.sequence = 5

        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product_mts.id,
                "location_id": self.location.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 5.0,
                "product_max_qty": 20.0,
                "trigger": "manual",
            }
        )

        # Check that supplier_id is set to vendor2 (lower sequence)
        self.assertEqual(
            orderpoint.supplier_id,
            self.supplierinfo2,
            "Manual orderpoint should select vendor with lowest sequence",
        )

    def test_vendor_id_field_also_set(self):
        """Test that vendor_id field is also properly set when supplier_id is set."""
        orderpoint = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.product_mts.id,
                "location_id": self.location.id,
                "warehouse_id": self.warehouse.id,
                "product_min_qty": 5.0,
                "product_max_qty": 20.0,
                "trigger": "manual",
            }
        )

        # Check that supplier_id is set to first vendor's supplierinfo
        self.assertEqual(
            orderpoint.supplier_id,
            self.supplierinfo1,
            "supplier_id should be set to first vendor's supplierinfo",
        )

        # Check that the partner (vendor) is accessible through supplier_id
        self.assertEqual(
            orderpoint.supplier_id.partner_id,
            self.vendor1,
            "supplier_id.partner_id should be the first vendor",
        )
