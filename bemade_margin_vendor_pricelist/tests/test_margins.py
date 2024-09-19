from odoo.tests import TransactionCase, tagged
from unittest.mock import patch, PropertyMock


@tagged("-at_install", "post_install")
class TestSaleOrderLine(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a test vendor
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Test Vendor',
            'supplier_rank': 1,
        })

        # Create a test product
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'type': 'product',
            'list_price': 100.0,
            'standard_price': 80.0,
        })

        # Link supplier info to the product
        cls.supplierinfo = cls.env['product.supplierinfo'].create({
            'partner_id': cls.vendor.id,
            'product_tmpl_id': cls.product.product_tmpl_id.id,
            'min_qty': 1,
            'price': 75.0,  # Vendor price
            'currency_id': cls.env.ref('base.USD').id,  # Assuming USD for simplicity
        })

        # Create a test sale order
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.env.ref('base.res_partner_1').id,
            # Assuming a default partner
        })

        # Create a test sale order line
        cls.sale_order_line = cls.env['sale.order.line'].create({
            'order_id': cls.sale_order.id,
            'product_id': cls.product.id,
            'product_uom_qty': 10,
            'price_unit': 120.0,
        })

    def test_purchase_price_all_from_stock(self):
        """Test when all quantity is fulfilled from stock."""
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = 10  # All available

            # Recompute the fields
            self.sale_order_line._compute_actual_gp()

            # Assert purchase_price_actual equals purchase_price (from stock)
            self.assertEqual(
                self.sale_order_line.purchase_price_actual,
                self.sale_order_line.purchase_price,
                "Purchase price should be from stock when all quantity is available."
            )

            # Assert gross_profit is calculated correctly
            expected_gross_profit = self.sale_order_line.price_subtotal - (
                    self.sale_order_line.purchase_price_actual * self.sale_order_line.product_uom_qty
            )
            self.assertAlmostEqual(
                self.sale_order_line.gross_profit,
                expected_gross_profit,
                msg="Gross profit should be correctly calculated from stock purchase price."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def assertSaleOrderComputesLikeSaleOrderLine(self):
        self.assertAlmostEqual(
            self.sale_order_line.gross_profit,
            self.sale_order.gross_profit,
        )
        self.assertAlmostEqual(
            self.sale_order_line.gross_profit_percent,
            self.sale_order.gross_profit_percent,
        )

    def test_purchase_price_all_from_vendor(self):
        """Test when all quantity is fulfilled from vendor."""
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = 0

            # Assert purchase_price_actual equals purchase_price_vendor (from vendor)
            self.assertEqual(
                self.sale_order_line.purchase_price_actual,
                self.sale_order_line.purchase_price_vendor,
                "Purchase price should be from vendor when all quantity is missing from stock."
            )

            # Assert gross_profit is calculated correctly
            expected_gross_profit = self.sale_order_line.price_subtotal - (
                    self.sale_order_line.purchase_price_actual * self.sale_order_line.product_uom_qty
            )
            self.assertAlmostEqual(
                self.sale_order_line.gross_profit,
                expected_gross_profit,
                msg="Gross profit should be correctly calculated from vendor purchase price."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_purchase_price_mixed(self):
        """Test when quantity is partially fulfilled from stock and partially from vendor."""
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = 5
            # Calculate expected blended purchase price
            qty_from_vendor = 5
            qty_from_stock = 5
            expected_purchase_price = (
                                              (
                                                      qty_from_vendor * self.sale_order_line.purchase_price_vendor) +
                                              (
                                                      qty_from_stock * self.sale_order_line.purchase_price)
                                      ) / self.sale_order_line.product_uom_qty

            self.assertAlmostEqual(
                self.sale_order_line.purchase_price_actual,
                expected_purchase_price,
                msg="Purchase price should be a blend of stock and vendor prices."
            )

            # Assert gross_profit is calculated correctly
            expected_gross_profit = self.sale_order_line.price_subtotal - (
                    expected_purchase_price * self.sale_order_line.product_uom_qty
            )
            self.assertAlmostEqual(
                self.sale_order_line.gross_profit,
                expected_gross_profit,
                msg="Gross profit should be correctly calculated from blended purchase price."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_negative_available_stock_zero_qty_ordered(self):
        """We had a division by zero error with a zero product_uom_qty field
        and a negative available stock. This test aims to root out this and
        other possible causes of a div by zero error."""
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = -1  # Negative available stock

            # Set product_uom_qty to zero
            self.sale_order_line.product_uom_qty = 0
            # Recompute the fields
            self.sale_order_line._compute_actual_gp()

            # Assert gross_profit is 0
            self.assertEqual(
                self.sale_order_line.gross_profit,
                0.0,
                "Gross profit should be 0 when product_uom_qty is zero."
            )

            # Assert gross_profit_percent is 0
            self.assertEqual(
                self.sale_order_line.gross_profit_percent,
                0.0,
                "Gross profit percent should be 0 when product_uom_qty is zero."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_purchase_price_all_from_stock_confirmed(self):
        """Test when all quantity is fulfilled from stock."""
        self.sale_order.action_confirm()
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = 10  # All available

            # Recompute the fields
            self.sale_order_line._compute_actual_gp()

            # Assert purchase_price_actual equals purchase_price (from stock)
            self.assertEqual(
                self.sale_order_line.purchase_price_actual,
                self.sale_order_line.purchase_price,
                "Purchase price should be from stock when all quantity is available."
            )

            # Assert gross_profit is calculated correctly
            expected_gross_profit = self.sale_order_line.price_subtotal - (
                    self.sale_order_line.purchase_price_actual * self.sale_order_line.product_uom_qty
            )
            self.assertAlmostEqual(
                self.sale_order_line.gross_profit,
                expected_gross_profit,
                msg="Gross profit should be correctly calculated from stock purchase price."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_purchase_price_all_from_vendor_confirmed(self):
        """Test when all quantity is fulfilled from vendor."""
        self.sale_order.action_confirm()
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = 0

            # Assert purchase_price_actual equals purchase_price_vendor (from vendor)
            self.assertEqual(
                self.sale_order_line.purchase_price_actual,
                self.sale_order_line.purchase_price_vendor,
                "Purchase price should be from vendor when all quantity is missing from stock."
            )

            # Assert gross_profit is calculated correctly
            expected_gross_profit = self.sale_order_line.price_subtotal - (
                    self.sale_order_line.purchase_price_actual * self.sale_order_line.product_uom_qty
            )
            self.assertAlmostEqual(
                self.sale_order_line.gross_profit,
                expected_gross_profit,
                msg="Gross profit should be correctly calculated from vendor purchase price."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_purchase_price_mixed_confirmed(self):
        """Test when quantity is partially fulfilled from stock and partially from vendor."""
        self.sale_order.action_confirm()
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = 5
            # Calculate expected blended purchase price
            qty_from_vendor = 5
            qty_from_stock = 5
            expected_purchase_price = (
                                              (
                                                      qty_from_vendor * self.sale_order_line.purchase_price_vendor) +
                                              (
                                                      qty_from_stock * self.sale_order_line.purchase_price)
                                      ) / self.sale_order_line.product_uom_qty

            self.assertAlmostEqual(
                self.sale_order_line.purchase_price_actual,
                expected_purchase_price,
                msg="Purchase price should be a blend of stock and vendor prices."
            )

            # Assert gross_profit is calculated correctly
            expected_gross_profit = self.sale_order_line.price_subtotal - (
                    expected_purchase_price * self.sale_order_line.product_uom_qty
            )
            self.assertAlmostEqual(
                self.sale_order_line.gross_profit,
                expected_gross_profit,
                msg="Gross profit should be correctly calculated from blended purchase price."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_negative_available_stock_zero_qty_ordered_confirmed(self):
        """We had a division by zero error with a zero product_uom_qty field
        and a negative available stock. This test aims to root out this and
        other possible causes of a div by zero error."""
        self.sale_order.action_confirm()
        with patch.object(
                self.sale_order_line.product_id.__class__,
                "qty_available",
                new_callable=PropertyMock
        ) as mock_qty_available:
            mock_qty_available.return_value = -1  # Negative available stock

            # Set product_uom_qty to zero
            self.sale_order_line.product_uom_qty = 0
            # Recompute the fields
            self.sale_order_line._compute_actual_gp()

            # Assert gross_profit is 0
            self.assertEqual(
                self.sale_order_line.gross_profit,
                0.0,
                "Gross profit should be 0 when product_uom_qty is zero."
            )

            # Assert gross_profit_percent is 0
            self.assertEqual(
                self.sale_order_line.gross_profit_percent,
                0.0,
                "Gross profit percent should be 0 when product_uom_qty is zero."
            )
            # Ensure the SO is correct as well
            self.assertSaleOrderComputesLikeSaleOrderLine()

    def test_determine_missing_stock_all_reserved(self):
        """Test the actual _determine_missing_stock method when all stock is reserved."""
        # Set initial stock for the product
        location = self.env["stock.warehouse"].search([])[0].lot_stock_id
        quant = self.env["stock.quant"].create({
            "product_id": self.product.id,
            "location_id": location.id,
            "inventory_quantity": 10,
            "product_uom_id": self.product.uom_id.id,
        })
        quant.action_apply_inventory()

        self.sale_order.action_confirm()
        # Force the move to be reserved
        self.sale_order.picking_ids.action_assign()

        # Now, call _determine_missing_stock without mocking
        missing_stock = self.sale_order_line._determine_missing_stock()

        # Assert that missing_stock is 0
        self.assertEqual(
            missing_stock,
            0,
            "_determine_missing_stock should return 0 when all stock is reserved."
        )

        # Additionally, verify that purchase_price_actual is from stock
        self.sale_order_line._compute_actual_gp()

        self.assertEqual(
            self.sale_order_line.purchase_price_actual,
            self.sale_order_line.purchase_price,
            "Purchase price should be from stock when all stock is reserved."
        )

        # Assert gross_profit is calculated correctly
        expected_gross_profit = self.sale_order_line.price_subtotal - (
                self.sale_order_line.purchase_price_actual * self.sale_order_line.product_uom_qty
        )
        self.assertAlmostEqual(
            self.sale_order_line.gross_profit,
            expected_gross_profit,
            msg="Gross profit should be correctly calculated when all stock is reserved."
        )

        # Assert gross_profit_percent is calculated correctly
        if self.sale_order_line.price_subtotal:
            expected_gross_profit_percent = self.sale_order_line.gross_profit / self.sale_order_line.price_subtotal
        else:
            expected_gross_profit_percent = 0.0

        self.assertAlmostEqual(
            self.sale_order_line.gross_profit_percent,
            expected_gross_profit_percent,
            msg="Gross profit percent should be correctly calculated when all stock is reserved."
        )
        # Ensure the SO is correct as well
        self.assertSaleOrderComputesLikeSaleOrderLine()
