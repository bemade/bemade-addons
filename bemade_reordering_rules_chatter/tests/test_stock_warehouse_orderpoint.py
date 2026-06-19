from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStockWarehouseOrderpoint(TransactionCase):
    def test_orderpoint_model_loaded(self):
        """Test that stock.warehouse.orderpoint model is loaded"""
        orderpoint_model = self.env["stock.warehouse.orderpoint"]
        self.assertIsNotNone(orderpoint_model)

    def test_orderpoint_has_chatter_fields(self):
        """Test that orderpoint has mail.thread fields"""
        orderpoint_model = self.env["stock.warehouse.orderpoint"]
        self.assertTrue(hasattr(orderpoint_model, "message_ids"))
        self.assertTrue(hasattr(orderpoint_model, "activity_ids"))
