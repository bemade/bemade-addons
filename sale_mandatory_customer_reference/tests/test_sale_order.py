from odoo.tests import tagged
from odoo.exceptions import ValidationError

from odoo.addons.payment.tests.common import PaymentCommon


@tagged("post_install", "-at_install")
class TestSaleOrder(PaymentCommon):

    def setUp(self):
        super().setUp()
        # Create test payment provider
        self.payment_provider = self._prepare_provider()
        # Create test payment method
        self.payment_method = self.env["payment.method"].create(
            {
                "name": "Test Card",
                "code": "card",
            }
        )

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "email": "test@example.com",
            }
        )
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "consu",
                "invoice_policy": "order",
            }
        )
        self.sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )

    def test_confirm_without_reference_disabled(self):
        """Test that order can be confirmed without reference when setting is disabled."""
        # Ensure setting is disabled
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", False
        )

        # Set delivery_billing_mode to satisfy pneumac_sale constraint
        self.sale_order.delivery_billing_mode = "ppc"

        # Should confirm without error
        self.sale_order.with_context(skip_tax_warning=True).action_confirm()
        self.assertEqual(self.sale_order.state, "sale")

    def test_confirm_without_reference_enabled(self):
        """Test that order cannot be confirmed without reference when setting is enabled."""
        # Enable the setting
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )

        # Set delivery_billing_mode to satisfy pneumac_sale constraint
        self.sale_order.delivery_billing_mode = "ppc"

        # Should raise ValidationError
        with self.assertRaises(ValidationError):
            self.sale_order.with_context(skip_tax_warning=True).action_confirm()

    def test_confirm_with_reference_enabled(self):
        """Test that order can be confirmed with reference when setting is enabled."""
        # Enable the setting
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )

        # Set customer reference and delivery_billing_mode
        self.sale_order.client_order_ref = "PO001"
        self.sale_order.delivery_billing_mode = "ppc"

        # Should confirm without error
        self.sale_order.with_context(skip_tax_warning=True).action_confirm()
        self.assertEqual(self.sale_order.state, "sale")

    def test_confirm_online_payment_without_reference(self):
        """Test that online payments auto-set reference to 'Credit Card'."""
        # Enable the setting
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )

        # Create a mock transaction
        transaction = self.env["payment.transaction"].create(
            {
                "reference": "Test Transaction",
                "partner_id": self.partner.id,
                "amount": 100,
                "currency_id": self.env.company.currency_id.id,
                "provider_id": self.payment_provider.id,
                "payment_method_id": self.payment_method.id,
                "state": "done",
                "partner_name": "Test Customer",
                "partner_email": "test@example.com",
            }
        )
        self.sale_order.transaction_ids = [(4, transaction.id)]

        # Set delivery_billing_mode to satisfy pneumac_sale constraint
        self.sale_order.delivery_billing_mode = "ppc"

        # Should confirm without error and set reference
        self.sale_order.with_context(skip_tax_warning=True).action_confirm()
        self.assertEqual(self.sale_order.state, "sale")
        self.assertEqual(self.sale_order.client_order_ref, "Credit Card")
