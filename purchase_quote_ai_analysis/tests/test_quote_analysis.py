import json
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.purchase_quote_ai_analysis.wizard.quote_analysis_wizard import (
    PurchaseQuoteAnalysisWizard,
)


@tagged("-at_install", "post_install")
class TestQuoteAnalysis(TransactionCase):
    """Quote-analysis wizard against a mocked DeepSeek response, modelled on a
    real vendor quote (net prices after discount, a fuel-surcharge fee line,
    and a transport amount in the footer)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.vendor = env['res.partner'].create({
            'name': 'Quote Vendor', 'is_company': True,
        })
        cls.product_a = env['product.product'].create({
            'name': 'QA Product A', 'type': 'consu',
        })
        cls.product_b = env['product.product'].create({
            'name': 'QA Product B', 'type': 'consu',
        })
        cls.fee_transport = env['product.product'].create({
            'name': 'QA Transport', 'type': 'service',
        })
        cls.fee_surcharge = env['product.product'].create({
            'name': 'QA Fuel Surcharge', 'type': 'service',
        })
        cls.po = env['purchase.order'].create({
            'partner_id': cls.vendor.id,
            'order_line': [
                Command.create({
                    'product_id': cls.product_a.id, 'product_qty': 2, 'price_unit': 0.0,
                }),
                Command.create({
                    'product_id': cls.product_b.id, 'product_qty': 1, 'price_unit': 0.0,
                }),
            ],
        })

    RESPONSE = {
        'line_items': [
            {'po_line_index': 0, 'description': 'Product A', 'qty': 2.0, 'unit_price': 12.334},
            {'po_line_index': 1, 'description': 'Product B', 'qty': 1.0, 'unit_price': 66.6},
        ],
        'landed_costs': [
            {'description': 'Surcharge de carburant', 'amount': 1.0},
            {'description': 'Transport', 'amount': 16.25},
        ],
        'untaxed_total': 108.518,
    }

    def _run_wizard(self, response=None, apply_landed=True, map_products=True):
        wizard = self.env['purchase.quote.analysis.wizard'].create({
            'purchase_order_id': self.po.id,
            'input_mode': 'text',
            'quote_text': 'mocked quote text',
        })
        with patch.object(
            PurchaseQuoteAnalysisWizard, '_call_deepseek',
            return_value=json.dumps(response or self.RESPONSE),
        ):
            wizard.action_analyse()
        wizard.action_apply_prices()
        if wizard.state == 'review_landed' and apply_landed:
            if map_products:
                for lc in wizard.landed_cost_ids:
                    lc.product_id = (
                        self.fee_surcharge if 'urcharge' in lc.description else self.fee_transport
                    )
            wizard.action_apply_landed_costs()
        return wizard

    def test_prices_applied_rounded(self):
        """Quoted prices land on the PO lines and supplierinfo rounded to the
        Product Price precision."""
        self._run_wizard()
        line_a = self.po.order_line.filtered(lambda l: l.product_id == self.product_a)
        self.assertEqual(line_a.price_unit, 12.33, "12.334 must round to 12.33")
        line_b = self.po.order_line.filtered(lambda l: l.product_id == self.product_b)
        self.assertEqual(line_b.price_unit, 66.6)
        seller = self.product_a.product_tmpl_id.seller_ids.filtered(
            lambda s: s.partner_id == self.vendor)
        self.assertEqual(seller.price, 12.33)

    def test_landed_costs_added_to_po(self):
        """Fee lines are created on the PO so its total matches the quote."""
        self._run_wizard()
        fee_lines = self.po.order_line.filtered(
            lambda l: l.product_id in (self.fee_transport | self.fee_surcharge))
        self.assertEqual(len(fee_lines), 2)
        by_product = {l.product_id: l for l in fee_lines}
        self.assertEqual(by_product[self.fee_surcharge].price_unit, 1.0)
        self.assertEqual(by_product[self.fee_transport].price_unit, 16.25)
        self.assertEqual(by_product[self.fee_transport].product_qty, 1)

    def test_reanalysis_is_idempotent(self):
        """Running the analysis twice must not duplicate fee lines; amounts
        are updated in place."""
        self._run_wizard()
        n_lines = len(self.po.order_line)
        updated = dict(self.RESPONSE)
        updated['landed_costs'] = [
            {'description': 'Surcharge de carburant', 'amount': 2.0},
            {'description': 'Transport', 'amount': 18.0},
        ]
        self._run_wizard(response=updated)
        self.assertEqual(len(self.po.order_line), n_lines,
                         "re-analysis must not append duplicate fee lines")
        transport = self.po.order_line.filtered(lambda l: l.product_id == self.fee_transport)
        self.assertEqual(transport.price_unit, 18.0)

    def test_manual_fee_line_adopted(self):
        """A fee line the buyer already added by hand is updated, not doubled."""
        self.env['purchase.order.line'].create({
            'order_id': self.po.id,
            'product_id': self.fee_transport.id,
            'name': 'Transport (manual)',
            'product_qty': 1,
            'product_uom_id': self.fee_transport.uom_id.id,
            'price_unit': 99.0,
        })
        self._run_wizard()
        transport_lines = self.po.order_line.filtered(
            lambda l: l.product_id == self.fee_transport)
        self.assertEqual(len(transport_lines), 1)
        self.assertEqual(transport_lines.price_unit, 16.25)

    def test_unmapped_landed_cost_raises(self):
        """An applied landed cost without a product must raise, not vanish."""
        with self.assertRaises(UserError):
            self._run_wizard(map_products=False)

    def test_unapplied_landed_cost_ignored_and_logged(self):
        """Unticked landed costs are skipped and listed in the chatter."""
        wizard = self.env['purchase.quote.analysis.wizard'].create({
            'purchase_order_id': self.po.id,
            'input_mode': 'text',
            'quote_text': 'mocked',
        })
        with patch.object(
            PurchaseQuoteAnalysisWizard, '_call_deepseek',
            return_value=json.dumps(self.RESPONSE),
        ):
            wizard.action_analyse()
        wizard.action_apply_prices()
        surcharge_lc = wizard.landed_cost_ids.filtered(
            lambda l: 'urcharge' in l.description)
        surcharge_lc.apply = False
        transport_lc = wizard.landed_cost_ids - surcharge_lc
        transport_lc.product_id = self.fee_transport
        wizard.action_apply_landed_costs()

        self.assertFalse(self.po.order_line.filtered(
            lambda l: l.product_id == self.fee_surcharge))
        note = self.po.message_ids.filtered(
            lambda m: 'Ignored' in (m.body or ''))
        self.assertTrue(note, "ignored landed costs must be listed in chatter")

    def test_total_sanity_check_mismatch_flagged(self):
        """A quote total that doesn't match the PO after apply posts a warning."""
        bad_total = dict(self.RESPONSE, untaxed_total=999.99)
        self._run_wizard(response=bad_total)
        warning = self.po.message_ids.filtered(
            lambda m: 'differs from the vendor' in (m.body or ''))
        self.assertTrue(warning)

    def test_total_sanity_check_match(self):
        """A matching total posts the confirmation note. PO total after apply:
        2×12.33 + 66.60 + 1.00 + 16.25 = 108.51."""
        good_total = dict(self.RESPONSE, untaxed_total=108.51)
        self._run_wizard(response=good_total)
        ok_note = self.po.message_ids.filtered(
            lambda m: 'matches the vendor quote' in (m.body or ''))
        self.assertTrue(ok_note)

    def test_discrepancies_detected(self):
        """Missing / extra / qty-mismatch discrepancies are surfaced."""
        response = {
            'line_items': [
                {'po_line_index': 0, 'description': 'Product A', 'qty': 5.0, 'unit_price': 12.0},
                {'po_line_index': -1, 'description': 'Unknown thing', 'qty': 1.0, 'unit_price': 3.0},
            ],
            'landed_costs': [],
            'untaxed_total': 0.0,
        }
        wizard = self.env['purchase.quote.analysis.wizard'].create({
            'purchase_order_id': self.po.id,
            'input_mode': 'text',
            'quote_text': 'mocked',
        })
        with patch.object(
            PurchaseQuoteAnalysisWizard, '_call_deepseek',
            return_value=json.dumps(response),
        ):
            wizard.action_analyse()
        types = wizard.discrepancy_ids.mapped('discrepancy_type')
        self.assertIn('missing', types)   # product_b absent from quote
        self.assertIn('extra', types)     # unmatched quote line
        self.assertIn('qty_mismatch', types)  # 5 quoted vs 2 on RFQ
