import json
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import float_compare


@tagged("-at_install", "post_install")
class TestQuoteAnalysis(TransactionCase):
    """Vendor-quote analyzer: price rounding, landed-cost fee lines on the PO,
    dedup/idempotency, mapping guards, and the after-apply hook.

    This module is generic (depends on ``purchase`` only) so the tests never
    touch Sales; the fee-line SO mirror is a downstream concern verified in the
    module that overrides the hook.

    DeepSeek is mocked — no live API is ever called.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env["ir.config_parameter"].sudo().set_param(
            "purchase_quote_ai_analysis.deepseek_api_key", "test-key")

        cls.vendor = env["res.partner"].create({
            "name": "QA Vendor", "is_company": True})
        cls.uom_unit = env.ref("uom.product_uom_unit")

        cls.product = env["product.product"].create({
            "name": "QA Widget", "type": "consu",
            "uom_id": cls.uom_unit.id, "list_price": 50.0})
        cls.freight = env["product.product"].create({
            "name": "QA Freight", "type": "service",
            "uom_id": cls.uom_unit.id, "list_price": 0.0})

    def _make_po(self):
        return self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "order_line": [(0, 0, {
                "product_id": self.product.id,
                "name": self.product.name,
                "product_qty": 3,
                "product_uom_id": self.uom_unit.id,
                "price_unit": 0.0,
            })],
        })

    def _wizard(self, po):
        action = po.action_analyse_quote()
        Wizard = self.env[action["res_model"]].with_context(action["context"])
        return Wizard.create({"input_mode": "text", "quote_text": "irrelevant"})

    def _analyse(self, wizard, line_items, landed_costs, total=None):
        payload = {"line_items": line_items, "landed_costs": landed_costs}
        if total is not None:
            payload["total"] = total
        with patch.object(type(wizard), "_call_deepseek",
                          return_value=json.dumps(payload)):
            wizard.action_analyse()

    def test_api_key_legacy_fallback(self):
        """The legacy fitcrew parameter is still honoured as a fallback."""
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_quote_ai_analysis.deepseek_api_key", "")
        self.env["ir.config_parameter"].sudo().set_param(
            "fitcrew_supply_workflow.deepseek_api_key", "legacy-key")
        po = self._make_po()
        wizard = self._wizard(po)
        self.assertEqual(wizard._get_api_key(), "legacy-key")
        # Restore for the other tests.
        self.env["ir.config_parameter"].sudo().set_param(
            "purchase_quote_ai_analysis.deepseek_api_key", "test-key")
        self.env["ir.config_parameter"].sudo().set_param(
            "fitcrew_supply_workflow.deepseek_api_key", "")

    def test_apply_prices_rounds(self):
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 12.333}],
            [],
        )
        wizard.action_apply_prices()
        po_line = po.order_line.filtered(lambda l: l.product_id == self.product)
        self.assertEqual(round(po_line.price_unit, 2), po_line.price_unit,
                         "PO price must be rounded to Product Price precision.")
        seller = self.product.seller_ids.filtered(
            lambda s: s.partner_id == self.vendor)
        self.assertTrue(seller)
        self.assertEqual(round(seller.price, 2), seller.price,
                         "Supplierinfo price must be rounded too.")

    def test_landed_cost_fee_line_on_po(self):
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 100.0}],
        )
        wizard.action_apply_prices()
        wizard.landed_cost_ids.write({"product_id": self.freight.id})
        wizard.action_apply_landed_costs()

        # Fee line on the PO, flagged, deduped, priced to the quote.
        po_fee = po.order_line.filtered(lambda l: l.product_id == self.freight)
        self.assertEqual(len(po_fee), 1)
        self.assertTrue(po_fee.is_landed_cost_fee)
        self.assertEqual(float_compare(po_fee.price_unit, 100.0, 2), 0)
        self.assertEqual(po_fee.product_qty, 1)

    def test_hook_receives_fee_lines(self):
        """The after-apply hook fires with the created fee-line recordset."""
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 80.0}],
        )
        wizard.action_apply_prices()
        wizard.landed_cost_ids.write({"product_id": self.freight.id})

        seen = {}

        def _spy(self_po, fee_lines):
            seen["lines"] = fee_lines

        with patch.object(type(po), "_post_apply_landed_costs", _spy):
            wizard.action_apply_landed_costs()

        self.assertIn("lines", seen)
        self.assertEqual(seen["lines"].product_id, self.freight)
        self.assertTrue(seen["lines"].is_landed_cost_fee)

    def test_reanalysis_is_idempotent(self):
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 100.0}],
        )
        wizard.action_apply_prices()
        wizard.landed_cost_ids.write({"product_id": self.freight.id})
        wizard.action_apply_landed_costs()

        # Re-run the whole analysis with a corrected freight amount.
        wizard2 = self._wizard(po)
        self._analyse(
            wizard2,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 120.0}],
        )
        wizard2.action_apply_prices()
        wizard2.landed_cost_ids.write({"product_id": self.freight.id})
        wizard2.action_apply_landed_costs()

        po_fee = po.order_line.filtered(lambda l: l.product_id == self.freight)
        self.assertEqual(len(po_fee), 1, "Re-analysis must not duplicate the PO fee line.")
        self.assertEqual(float_compare(po_fee.price_unit, 120.0, 2), 0,
                         "Re-analysis must update the fee amount in place.")

    def test_reanalysis_does_not_flag_fee_line_as_discrepancy(self):
        """On re-analysis, the existing fee line must not be matched as a
        product line nor surface as a 'missing from quote' discrepancy."""
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 100.0}],
        )
        wizard.action_apply_prices()
        wizard.landed_cost_ids.write({"product_id": self.freight.id})
        wizard.action_apply_landed_costs()

        wizard2 = self._wizard(po)
        self._analyse(
            wizard2,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 100.0}],
        )
        # The freight fee line is excluded from the matchable RFQ lines, so no
        # discrepancy points at it.
        self.assertFalse(
            wizard2.discrepancy_ids.filtered(
                lambda d: d.po_line_id.product_id == self.freight),
            "The landed-cost fee line must not be treated as a product line.",
        )

    def test_unmapped_applied_landed_cost_raises(self):
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Mystery Fee", "amount": 50.0}],
        )
        wizard.action_apply_prices()
        self.assertTrue(all(lc.apply for lc in wizard.landed_cost_ids))
        self.assertFalse(wizard.landed_cost_ids.product_id)
        with self.assertRaises(UserError):
            wizard.action_apply_landed_costs()

    def test_unapplied_landed_cost_is_ignored(self):
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Optional Fee", "amount": 50.0}],
        )
        wizard.action_apply_prices()
        wizard.landed_cost_ids.write({"apply": False})
        wizard.action_apply_landed_costs()  # must not raise
        po_fee = po.order_line.filtered(lambda l: l.product_id == self.freight)
        self.assertFalse(po_fee, "apply=False landed cost must not create a fee line.")

    def test_sanity_note_on_total_gap(self):
        """A stated quote total that differs from the PO total posts a warning."""
        po = self._make_po()
        wizard = self._wizard(po)
        self._analyse(
            wizard,
            [{"po_line_index": 0, "description": "QA Widget",
              "qty": 3.0, "unit_price": 10.0}],
            [{"description": "Freight", "amount": 100.0}],
            total=999.0,
        )
        wizard.action_apply_prices()
        wizard.landed_cost_ids.write({"product_id": self.freight.id})
        wizard.action_apply_landed_costs()
        # PO untaxed = 3*10 + 100 = 130, quote states 999 -> gap warning posted.
        bodies = " ".join(po.message_ids.mapped("body"))
        self.assertIn("Sanity check", bodies)
