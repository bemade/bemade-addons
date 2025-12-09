from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleLateNotification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "type": "consu"}
        )
        cls.user = cls.env["res.users"].create(
            {
                "name": "Test User",
                "login": "test_late_notification_user",
                "email": "test@example.com",
            }
        )

        # Set config parameters for sale
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.sale_late_days_threshold", "5"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.sale_activity_summary",
            "Vérifier commande en retard",
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.sale_default_user_id", str(cls.user.id)
        )

    def _create_sale_order(self, expected_ship_date):
        """Helper to create a confirmed sale order with a given expected ship date."""
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
                            "price_unit": 100,
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        # Set expected_ship_date directly on the line after confirmation
        order.order_line.expected_ship_date = expected_ship_date
        return order

    def test_late_sale_order_creates_activity(self):
        """Test that a late sale order gets an activity created."""
        # Create an order with expected ship date 6 days ago (past the 5-day threshold)
        late_date = fields.Date.today() - timedelta(days=6)
        order = self._create_sale_order(late_date)

        # Verify order is marked as late
        self.assertTrue(order.is_late, "Order should be marked as late")

        # Run the cron
        self.env["sale.order"]._cron_create_late_activities()

        # Check that an activity was created and notification date was set
        self.assertTrue(
            order.late_notification_date,
            "Late notification date should be set",
        )
        self.assertEqual(
            len(order.activity_ids),
            1,
            "One late notification activity should be created",
        )
        self.assertEqual(
            order.activity_ids.user_id,
            self.user,
            "Activity should be assigned to configured user",
        )

    def test_late_sale_order_not_renotified(self):
        """Test that running cron again does not create duplicate activities."""
        # Create a late order
        late_date = fields.Date.today() - timedelta(days=6)
        order = self._create_sale_order(late_date)

        # Run the cron twice
        self.env["sale.order"]._cron_create_late_activities()
        self.env["sale.order"]._cron_create_late_activities()

        # Check that only one activity was created
        self.assertEqual(
            len(order.activity_ids),
            1,
            "Only one late notification activity should exist after multiple cron runs",
        )

    def test_not_late_order_no_activity(self):
        """Test that orders within threshold don't get activities."""
        # Create an order that is only 3 days late (within 5-day threshold)
        recent_date = fields.Date.today() - timedelta(days=3)
        order = self._create_sale_order(recent_date)

        # Run the cron
        self.env["sale.order"]._cron_create_late_activities()

        # Check that no activity was created and no notification date
        self.assertFalse(
            order.late_notification_date,
            "Late notification date should not be set",
        )
        self.assertEqual(
            len(order.activity_ids),
            0,
            "No activity should be created for orders not yet late",
        )


@tagged("post_install", "-at_install")
class TestPurchaseLateNotification(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Product", "type": "consu"}
        )
        cls.user = cls.env["res.users"].create(
            {
                "name": "Test Purchase User",
                "login": "test_late_notification_purchase_user",
                "email": "test_purchase@example.com",
            }
        )

        # Set config parameters for purchase
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.purchase_late_days_threshold", "5"
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.purchase_activity_summary",
            "Vérifier commande en retard",
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "sale_purchase_late_notification.purchase_default_user_id", str(cls.user.id)
        )

    def _create_purchase_order(self, date_planned):
        """Helper to create a confirmed purchase order with a given planned date."""
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_qty": 1,
                            "price_unit": 100,
                            "name": self.product.name,
                            "date_planned": date_planned,
                        },
                    )
                ],
            }
        )
        order.button_confirm()
        return order

    def test_late_purchase_order_creates_activity(self):
        """Test that a late purchase order gets an activity created."""
        # Create an order that is 6 days late
        late_date = fields.Datetime.now() - timedelta(days=6)
        order = self._create_purchase_order(late_date)

        # Verify order is marked as late
        self.assertTrue(order.is_late, "Order should be marked as late")

        # Run the cron
        self.env["purchase.order"]._cron_create_late_activities()

        # Check that an activity was created and notification date was set
        self.assertTrue(
            order.late_notification_date,
            "Late notification date should be set",
        )
        self.assertEqual(
            len(order.activity_ids),
            1,
            "One late notification activity should be created",
        )
        self.assertEqual(
            order.activity_ids.user_id,
            self.user,
            "Activity should be assigned to configured user",
        )

    def test_late_purchase_order_not_renotified(self):
        """Test that running cron again does not create duplicate activities."""
        # Create a late order
        late_date = fields.Datetime.now() - timedelta(days=6)
        order = self._create_purchase_order(late_date)

        # Run the cron twice
        self.env["purchase.order"]._cron_create_late_activities()
        self.env["purchase.order"]._cron_create_late_activities()

        # Check that only one activity was created
        self.assertEqual(
            len(order.activity_ids),
            1,
            "Only one late notification activity should exist after multiple cron runs",
        )

    def test_not_late_purchase_order_no_activity(self):
        """Test that orders within threshold don't get activities."""
        # Create an order that is only 3 days late
        recent_date = fields.Datetime.now() - timedelta(days=3)
        order = self._create_purchase_order(recent_date)

        # Run the cron
        self.env["purchase.order"]._cron_create_late_activities()

        # Check that no activity was created and no notification date
        self.assertFalse(
            order.late_notification_date,
            "Late notification date should not be set",
        )
        self.assertEqual(
            len(order.activity_ids),
            0,
            "No activity should be created for orders within threshold",
        )
