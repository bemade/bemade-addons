# Copyright 2025 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from datetime import datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestPurchaseSyncReceiptDate(TransactionCase):
    """Test cases for purchase_sync_receipt_date module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a storable product (consumable type to trigger stock moves)
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "purchase_ok": True,
            }
        )

        # Create a vendor
        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Test Vendor",
                "supplier_rank": 1,
            }
        )

        # Get the default picking type
        cls.picking_type = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("warehouse_id.company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )

        # Set initial dates
        cls.initial_date = datetime.now() + timedelta(days=7)
        cls.updated_date = datetime.now() + timedelta(days=14)

    def _create_purchase_order(self, date_planned=None):
        """Helper to create a purchase order with one line."""
        if date_planned is None:
            date_planned = self.initial_date

        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "picking_type_id": self.picking_type.id,
            }
        )

        self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "product_id": self.product.id,
                "product_qty": 10.0,
                "price_unit": 100.0,
                "date_planned": date_planned,
            }
        )

        return po

    def test_sync_disabled_by_default(self):
        """Test that sync is disabled by default."""
        self.assertFalse(
            self.env.company.purchase_sync_receipt_date,
            "Sync should be disabled by default",
        )

    def test_sync_when_disabled(self):
        """Test that scheduled date is NOT synced when setting is disabled."""
        # Ensure setting is disabled
        self.env.company.purchase_sync_receipt_date = False

        # Create and confirm PO
        po = self._create_purchase_order()
        po.button_confirm()

        # Get the receipt and its moves
        picking = po.picking_ids
        self.assertTrue(picking, "Receipt should be created")
        moves = picking.move_ids
        self.assertTrue(moves, "Stock moves should be created")

        # Store initial scheduled date
        initial_scheduled_date = picking.scheduled_date
        initial_move_date = moves[0].date

        # Update PO line date
        po.order_line.write({"date_planned": self.updated_date})

        # Verify scheduled date was NOT updated (only deadline was updated)
        picking.invalidate_recordset()
        moves.invalidate_recordset()

        self.assertEqual(
            picking.scheduled_date,
            initial_scheduled_date,
            "Scheduled date should NOT change when sync is disabled",
        )
        self.assertEqual(
            moves[0].date,
            initial_move_date,
            "Move date should NOT change when sync is disabled",
        )

    def test_sync_when_enabled(self):
        """Test that scheduled date IS synced when setting is enabled."""
        # Enable the setting
        self.env.company.purchase_sync_receipt_date = True

        # Create and confirm PO
        po = self._create_purchase_order()
        po.button_confirm()

        # Get the receipt and its moves
        picking = po.picking_ids
        self.assertTrue(picking, "Receipt should be created")
        moves = picking.move_ids
        self.assertTrue(moves, "Stock moves should be created")

        # Update PO line date
        po.order_line.write({"date_planned": self.updated_date})

        # Verify scheduled date WAS updated
        picking.invalidate_recordset()
        moves.invalidate_recordset()

        self.assertEqual(
            moves[0].date,
            self.updated_date,
            "Move date should be updated when sync is enabled",
        )
        # Scheduled date is computed from move dates, so it should also update
        self.assertEqual(
            picking.scheduled_date,
            self.updated_date,
            "Scheduled date should be updated when sync is enabled",
        )

    def test_sync_only_pending_moves(self):
        """Test that only pending moves are updated, not done/cancelled ones."""
        # Enable the setting
        self.env.company.purchase_sync_receipt_date = True

        # Create and confirm PO
        po = self._create_purchase_order()
        po.button_confirm()

        # Get the receipt and validate it (mark as done)
        picking = po.picking_ids
        moves = picking.move_ids

        # Set quantities and validate
        for move in moves:
            move.quantity = move.product_uom_qty
        picking.button_validate()

        self.assertEqual(moves[0].state, "done", "Move should be done")

        # Store the done move's date
        done_move_date = moves[0].date

        # Try to update PO line date
        po.order_line.write({"date_planned": self.updated_date})

        # Verify done move date was NOT changed
        moves.invalidate_recordset()
        self.assertEqual(
            moves[0].date, done_move_date, "Done move date should NOT be updated"
        )

    def test_sync_with_multiple_lines(self):
        """Test sync with multiple PO lines."""
        # Enable the setting
        self.env.company.purchase_sync_receipt_date = True

        # Create PO with multiple lines
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "picking_type_id": self.picking_type.id,
            }
        )

        product2 = self.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "consu",
                "purchase_ok": True,
            }
        )

        line1 = self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "product_id": self.product.id,
                "product_qty": 10.0,
                "price_unit": 100.0,
                "date_planned": self.initial_date,
            }
        )

        line2 = self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "product_id": product2.id,
                "product_qty": 5.0,
                "price_unit": 50.0,
                "date_planned": self.initial_date,
            }
        )

        po.button_confirm()

        # Update only first line's date
        line1.write({"date_planned": self.updated_date})

        # Get moves for each line
        moves1 = line1.move_ids
        moves2 = line2.move_ids

        # Verify only first line's moves were updated
        self.assertEqual(
            moves1[0].date, self.updated_date, "First line's move should be updated"
        )
        self.assertEqual(
            moves2[0].date,
            self.initial_date,
            "Second line's move should NOT be updated",
        )

    def test_sync_ignores_display_type_lines(self):
        """Test that display type lines (sections/notes) are ignored."""
        # Enable the setting
        self.env.company.purchase_sync_receipt_date = True

        # Create PO with a section line
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "picking_type_id": self.picking_type.id,
            }
        )

        # Add a section line
        section_line = self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "display_type": "line_section",
                "name": "Test Section",
                "product_qty": 0,
            }
        )

        # Add a regular product line
        product_line = self.env["purchase.order.line"].create(
            {
                "order_id": po.id,
                "product_id": self.product.id,
                "product_qty": 10.0,
                "price_unit": 100.0,
                "date_planned": self.initial_date,
            }
        )

        po.button_confirm()

        # Update section line (should not cause any errors)
        section_line.write({"name": "Updated Section"})

        # Verify product line still works correctly
        product_line.write({"date_planned": self.updated_date})
        moves = product_line.move_ids

        self.assertEqual(
            moves[0].date, self.updated_date, "Product line's move should be updated"
        )

    def test_config_setting_persistence(self):
        """Test that the config setting persists correctly."""
        # Enable the setting
        config = self.env["res.config.settings"].create(
            {
                "purchase_sync_receipt_date": True,
            }
        )
        config.execute()

        # Verify it was saved to company
        self.assertTrue(
            self.env.company.purchase_sync_receipt_date,
            "Setting should be saved to company",
        )

        # Disable it
        config2 = self.env["res.config.settings"].create(
            {
                "purchase_sync_receipt_date": False,
            }
        )
        config2.execute()

        # Verify it was updated
        self.assertFalse(
            self.env.company.purchase_sync_receipt_date,
            "Setting should be updated on company",
        )
