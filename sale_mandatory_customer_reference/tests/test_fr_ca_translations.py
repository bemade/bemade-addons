"""
Odoo runtime test for fr_CA translations of sale_mandatory_customer_reference.

Acceptance criteria:
- When env lang is fr_CA and the enforce_customer_reference config parameter is
  enabled, calling action_confirm on a SO with no client_order_ref must raise a
  ValidationError whose message is the French translation.
- The French ValidationError message must be:
    "Une référence client (numéro de bon de commande) est requise avant de confirmer
     cette commande. Veuillez renseigner le champ de référence client."

NOTE: This test requires a full Odoo runtime with the fr_CA language installed.
It cannot be run in a standalone bemade-addons clone.  Run on staging/CI with:
    odoo-bin -d <db> --test-enable --test-tags=sale_mandatory_customer_reference.TestSaleMandatoryReferenceTranslations
or via odoo-dev test on the staging instance.
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestSaleMandatoryReferenceTranslations(
    # PaymentCommon is used in the existing test_sale_order.py; we keep the same
    # base class so setUp can reuse the payment-provider scaffolding if needed.
    # Import is deferred to avoid NameError in environments that lack the module.
):
    pass


# ---------------------------------------------------------------------------
# Re-define the class properly after the forward-reference workaround above is
# removed.  The class body below is the actual implementation.
# ---------------------------------------------------------------------------

try:
    from odoo.addons.payment.tests.common import PaymentCommon as _Base
except ImportError:
    from odoo.tests.common import TransactionCase as _Base  # fallback


@tagged("post_install", "-at_install")
class TestSaleMandatoryReferenceTranslations(_Base):  # noqa: F811
    """
    Verify that the fr_CA ValidationError message is correctly translated at
    Odoo runtime.
    """

    EXPECTED_FR_CA_MSG = (
        "Une référence client (numéro de bon de commande) est requise avant de confirmer"
        " cette commande. Veuillez renseigner le champ de référence client."
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Ensure the fr_CA language is active; install it if missing.
        fr_ca = cls.env["res.lang"].with_context(active_test=False).search(
            [("code", "=", "fr_CA")]
        )
        if fr_ca and not fr_ca.active:
            fr_ca.active = True
        # Load translations for this module into the database.
        cls.env["ir.translation"].load_module_terms(
            ["sale_mandatory_customer_reference"], ["fr_CA"]
        )

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Portal Customer",
                "email": "portal-test@example.com",
                "lang": "fr_CA",
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
        # Enable the customer-reference enforcement setting.
        self.env["ir.config_parameter"].sudo().set_param(
            "sale_mandatory_customer_reference.enforce_customer_reference", True
        )

    @mute_logger("odoo.addons.sale_mandatory_customer_reference")
    def test_validation_error_message_is_french_when_lang_fr_ca(self):
        """
        action_confirm on a SO with no client_order_ref, run under lang=fr_CA,
        must raise a ValidationError with the French translation.
        """
        env_fr = self.env(context={"lang": "fr_CA"})
        order_fr = self.sale_order.with_env(env_fr)

        with self.assertRaises(ValidationError) as ctx:
            order_fr.with_context(skip_tax_warning=True).action_confirm()

        actual_msg = str(ctx.exception.args[0]) if ctx.exception.args else ""
        self.assertEqual(
            actual_msg,
            self.EXPECTED_FR_CA_MSG,
            f"ValidationError message in fr_CA context was not translated.\n"
            f"  expected: {self.EXPECTED_FR_CA_MSG!r}\n"
            f"  actual:   {actual_msg!r}",
        )

    @mute_logger("odoo.addons.sale_mandatory_customer_reference")
    def test_validation_error_message_is_english_without_lang_context(self):
        """
        action_confirm on a SO with no client_order_ref, run without a fr_CA
        lang context, must raise a ValidationError with the English source string.
        """
        EXPECTED_EN_MSG = (
            "Customer reference (PO Number) is required before confirming this order. "
            "Please set the customer reference field."
        )

        with self.assertRaises(ValidationError) as ctx:
            self.sale_order.with_context(skip_tax_warning=True).action_confirm()

        actual_msg = str(ctx.exception.args[0]) if ctx.exception.args else ""
        self.assertEqual(
            actual_msg,
            EXPECTED_EN_MSG,
            f"ValidationError message without lang context was unexpected.\n"
            f"  expected: {EXPECTED_EN_MSG!r}\n"
            f"  actual:   {actual_msg!r}",
        )
