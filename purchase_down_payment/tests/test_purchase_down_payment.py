from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPurchaseDownPaymentSmoke(TransactionCase):
    """Smoke tests for purchase_down_payment.

    Cover the additions: `is_downpayment` flag on PO lines, the
    settings field for the default deposit product, and (when `sale`
    is installed, which contributes `product.invoice_policy`) the
    advance-payment wizard happy paths and basic validation.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The wizard's product check uses invoice_policy, a field added
        # by the `sale` module. Detect once so each test can skip cleanly
        # if it's missing.
        cls.has_invoice_policy = (
            "invoice_policy" in cls.env["product.template"]._fields
        )
        # Load a chart of accounts so account.move creation has a valid
        # default journal (needed by the wizard).
        if cls.has_invoice_policy:
            cls.env["account.chart.template"].try_loading(
                "generic_coa", company=cls.env.company, install_demo=False
            )

        cls.vendor = cls.env["res.partner"].create({"name": "DP Vendor"})
        cls.product = cls.env["product.product"].create({
            "name": "Buyable Widget",
            "default_code": "DP-W",
            "type": "consu",
            "purchase_ok": True,
            "list_price": 100.0,
            "standard_price": 80.0,
        })
        deposit_vals = {
            "name": "Down Payment",
            "type": "service",
            "purchase_ok": True,
        }
        if cls.has_invoice_policy:
            deposit_vals["invoice_policy"] = "order"
        cls.deposit_product = cls.env["product.product"].create(deposit_vals)

        cls.po = cls.env["purchase.order"].create({
            "partner_id": cls.vendor.id,
            "order_line": [(0, 0, {
                "product_id": cls.product.id,
                "product_qty": 10,
                "price_unit": 100.0,
            })],
        })
        cls.po.button_confirm()

    def _skip_if_no_invoice_policy(self):
        if not self.has_invoice_policy:
            self.skipTest("`sale` not installed: product.invoice_policy unavailable")

    # --- Field / setting smoke (no `sale` required) -------------------------

    def test_is_downpayment_field_on_po_line(self):
        """purchase.order.line gains a writable `is_downpayment` boolean."""
        line = self.po.order_line[0]
        self.assertFalse(line.is_downpayment)
        line.is_downpayment = True
        self.assertTrue(line.is_downpayment)

    def test_settings_deposit_product_field(self):
        """res.config.settings exposes po_deposit_default_product_id and
        persists it as an ir.config_parameter."""
        settings = self.env["res.config.settings"].create({
            "po_deposit_default_product_id": self.deposit_product.id,
        })
        settings.execute()
        param = self.env["ir.config_parameter"].sudo().get_param(
            "purchase_down_payment.po_deposit_default_product_id"
        )
        self.assertEqual(int(param), self.deposit_product.id)

    # --- Wizard happy paths (require `sale` for invoice_policy) -------------

    def _make_wizard(self, **values):
        return (
            self.env["purchase.order.advance.payment"]
            .with_context(active_model="purchase.order", active_ids=[self.po.id], active_id=self.po.id)
            .create(values)
        )

    def test_wizard_defaults_pull_currency_from_po(self):
        """When opened from a PO, the wizard defaults to that PO's currency."""
        wizard = self._make_wizard()
        self.assertEqual(wizard.currency_id, self.po.currency_id)

    def test_wizard_percentage_creates_downpayment_line_and_bill(self):
        """Percentage method appends a downpayment PO line and creates an
        in_invoice draft for the chosen percentage of the untaxed total."""
        self._skip_if_no_invoice_policy()
        wizard = self._make_wizard(
            advance_payment_method="percentage",
            amount=25.0,
            product_id=self.deposit_product.id,
        )
        result = wizard.action_create_advance_bill()
        self.assertIsInstance(result, dict)
        dp_lines = self.po.order_line.filtered("is_downpayment")
        self.assertEqual(len(dp_lines), 1)
        invoice = self.env["account.move"].search(
            [("invoice_origin", "=", self.po.name), ("move_type", "=", "in_invoice")],
            limit=1,
        )
        self.assertTrue(invoice)
        self.assertTrue(invoice.invoice_line_ids)
        self.assertGreater(invoice.invoice_line_ids[0].price_unit, 0)

    def test_wizard_fixed_amount_creates_downpayment_line_and_bill(self):
        """Fixed amount method behaves the same with an explicit value."""
        self._skip_if_no_invoice_policy()
        wizard = self._make_wizard(
            advance_payment_method="fixed",
            fixed_amount=150.0,
            product_id=self.deposit_product.id,
        )
        wizard.action_create_advance_bill()
        dp_lines = self.po.order_line.filtered("is_downpayment")
        self.assertEqual(len(dp_lines), 1)
        invoice = self.env["account.move"].search(
            [("invoice_origin", "=", self.po.name), ("move_type", "=", "in_invoice")],
            limit=1,
        )
        self.assertTrue(invoice)
        self.assertEqual(invoice.invoice_line_ids[0].price_unit, 150.0)

    def test_wizard_rejects_non_positive_percentage(self):
        """A 0% (or negative) down payment raises UserError before any
        record is created."""
        self._skip_if_no_invoice_policy()
        wizard = self._make_wizard(
            advance_payment_method="percentage",
            amount=0.0,
            product_id=self.deposit_product.id,
        )
        with self.assertRaises(UserError):
            wizard.action_create_advance_bill()

    def test_wizard_rejects_non_service_deposit_product(self):
        """If the configured deposit product is not a Service, the wizard
        refuses to create the down payment."""
        self._skip_if_no_invoice_policy()
        consumable = self.env["product.product"].create({
            "name": "Bad Deposit (consu)",
            "type": "consu",
            "invoice_policy": "order",
        })
        wizard = self._make_wizard(
            advance_payment_method="percentage",
            amount=10.0,
            product_id=consumable.id,
        )
        with self.assertRaises(UserError):
            wizard.action_create_advance_bill()
