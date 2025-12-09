from datetime import timedelta

from freezegun import freeze_time
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestExpectedShipDate(TransactionCase):
    """Test cases for expected_ship_date field on sale.order.line"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "sale_delay": 5}
        )

    @freeze_time("2024-01-10")
    def test_expected_ship_date_computed_from_lead_time(self):
        """Test that expected_ship_date is computed from order date + lead time"""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "customer_lead": 5,
                        },
                    )
                ],
            }
        )
        order.action_confirm()

        # Expected ship date should be order date + lead time
        expected_date = fields.Date.from_string("2024-01-15")
        self.assertEqual(
            order.order_line.expected_ship_date,
            expected_date,
            "Expected ship date should be order date + lead time",
        )

    @freeze_time("2024-01-10")
    def test_expected_ship_date_inverse_updates_lead_time(self):
        """Test that setting expected_ship_date updates customer_lead"""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "customer_lead": 5,
                        },
                    )
                ],
            }
        )

        # Set expected_ship_date to 10 days from now
        new_date = fields.Date.from_string("2024-01-20")
        order.order_line.expected_ship_date = new_date

        self.assertEqual(
            order.order_line.customer_lead,
            10,
            "Customer lead should be updated when expected_ship_date is set",
        )
