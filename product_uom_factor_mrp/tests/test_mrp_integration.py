"""
Integration tests for the delegation-design product_uom_factor MRP flow.

Tests cover (within mrp scope):
  - MRP BOM line in delegate-mL: MO raw move qty, move_line.quantity_product_uom
  - BOM line allowed_uom_ids scoping (crit 5 + refinement)
  - Crit 9 (scoping constraint path): cross-tree UoM on BOM line raises ValidationError;
    the uom.uom conversion-time guard was removed (review blocker 1+2).
  - Crit 10 regression: cross-tree _compute_quantity returns core's numeric result (no raise)
  - Edge cases: base-UoM change blocked, foreign==base rejected, factor persists,
    delegate cascade delete
  - Regression (crit 10): intra-category conversions unaffected; UC1-UC3 assertions

Domain: ink product (Unit base) with mL factor 0.00005.
        Cartridge BOM line: 250 mL-delegate per cartridge.
        250 delegate-mL × 0.00005 = 0.0125 Unit.

NOTE: valuation/SVL/COGS tests live in product_uom_factor_stock.
      PO tests live in product_uom_factor_purchase.
      SO/delivery tests live in product_uom_factor_sale.
"""

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests.common import TransactionCase


class TestMrpIntegrationBase(TransactionCase):
    """Common fixture for MRP integration tests.

    Ink product: base UoM = Unit, factor mL-delegate → 0.00005 Unit.
    Cartridge BOM: 250 delegate-mL per cartridge.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Enable UoM feature
        cls.env["res.config.settings"].create({"group_uom": True}).execute()

        # Ensure "Product Unit" decimal precision ≥ 5 for small factors (0.00005)
        dp = cls.env["decimal.precision"].search(
            [("name", "=", "Product Unit")], limit=1
        )
        if dp and dp.digits < 5:
            dp.digits = 5

        # ── UoMs ──────────────────────────────────────────────────────────────
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")
        cls.uom_liter = cls.env.ref("uom.product_uom_litre")

        # ── Company (needed for picking type lookup) ───────────────────────────
        cls.company = cls.env.company

        # ── Ink product ───────────────────────────────────────────────────────
        # In Odoo 19, type='consu' (Goods). type='product' removed. uom_po_id gone.
        cls.ink = cls.env["product.product"].create(
            {
                "name": "Test Ink – Cyan (MRP Integration)",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
            }
        )

        # ── Factor: 1 mL-delegate = 0.00005 Unit ─────────────────────────────
        cls.factor = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.ink.product_tmpl_id.id,
                "foreign_uom_id": cls.uom_ml.id,
                "factor": 0.00005,
            }
        )
        cls.delegate_ml = cls.factor.delegate_uom_id
        # Trigger additive sync so delegate is in uom_ids / allowed_uom_ids
        cls.ink.product_tmpl_id.write(
            {"uom_factor_ids": [(4, cls.factor.id)]}
        )

        # ── Cartridge product (finished) ──────────────────────────────────────
        cls.cartridge = cls.env["product.product"].create(
            {
                "name": "Test Cartridge (MRP Integration)",
                "type": "consu",
                "is_storable": True,
                "uom_id": cls.uom_unit.id,
            }
        )

        # ── BOM: 250 delegate-mL of ink per cartridge ─────────────────────────
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.cartridge.product_tmpl_id.id,
                "product_qty": 1.0,
                "product_uom_id": cls.uom_unit.id,
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.ink.id,
                            "product_qty": 250.0,
                            "product_uom_id": cls.delegate_ml.id,
                        },
                    )
                ],
            }
        )

        # ── Stock locations ────────────────────────────────────────────────────
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")


class TestDelegateIsUom(TestMrpIntegrationBase):
    """Crit 1 & 5 (unit test part): delegate IS a uom.uom in the product's tree."""

    def test_delegate_is_uom_instance(self):
        """The factor row's delegate_uom_id IS a uom.uom record."""
        self.assertIsInstance(
            self.delegate_ml,
            type(self.env["uom.uom"]),
            "delegate_uom_id must be a uom.uom record",
        )

    def test_delegate_relative_uom_is_base(self):
        """delegate.relative_uom_id == ink base UoM (Unit)."""
        self.assertEqual(
            self.delegate_ml.relative_uom_id,
            self.uom_unit,
            "Delegate's relative_uom_id must be the ink's base UoM (Unit)",
        )

    def test_delegate_relative_factor(self):
        """delegate.relative_factor == 0.00005."""
        self.assertAlmostEqual(
            self.delegate_ml.relative_factor,
            0.00005,
            places=8,
            msg="Delegate relative_factor must match the factor (0.00005)",
        )

    def test_delegate_has_common_reference_with_base(self):
        """delegate._has_common_reference(Unit) is True (intra-tree)."""
        self.assertTrue(
            self.delegate_ml._has_common_reference(self.uom_unit),
            "Delegate must share a common reference with the product's base UoM",
        )

    def test_delegate_in_product_uom_ids(self):
        """The delegate UoM is in the product template's uom_ids."""
        self.assertIn(
            self.delegate_ml,
            self.ink.product_tmpl_id.uom_ids,
            "Delegate must be in product template uom_ids after additive sync",
        )


class TestMrpMoConsumption(TestMrpIntegrationBase):
    """Crit 1 & 5 (full MRP flow): BOM line in delegate-mL → MO raw move qty correct."""

    def _stock_in(self, qty=1.0):
        """Put `qty` Units of ink into stock."""
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", self.company.id)],
            limit=1,
        )
        receipt = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": self.ink.id,
                            "product_uom": self.uom_unit.id,
                            "product_uom_qty": qty,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        }
                    )
                ],
            }
        )
        receipt.action_confirm()
        receipt.move_ids.quantity = qty
        receipt._action_done()
        return receipt

    def _make_mo(self, qty=1.0):
        """Create and confirm an MO for `qty` cartridges."""
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.cartridge.id,
                "product_qty": qty,
                "product_uom_id": self.uom_unit.id,
                "bom_id": self.bom.id,
            }
        )
        mo.action_confirm()
        return mo

    def test_mo_raw_move_qty_in_delegate_ml(self):
        """MO raw move: 250 delegate-mL BOM line → raw move in delegate-mL (product_uom_qty=250).

        In the delegation design, MRP creates the raw move in the BOM line's UoM
        (delegate-mL). The product_qty (computed base UoM) = 250 × 0.00005 = 0.0125 Unit.
        """
        self._stock_in(1.0)
        mo = self._make_mo(1.0)
        mo.action_assign()
        raw_move = mo.move_raw_ids.filtered(lambda m: m.product_id == self.ink)
        self.assertEqual(len(raw_move), 1, "Expected exactly one raw move for ink")
        # The move is in the BOM line's UoM (delegate-mL)
        self.assertEqual(
            raw_move.product_uom,
            self.delegate_ml,
            "Raw move product_uom must be the delegate-mL (BOM line UoM)",
        )
        # product_uom_qty = 250 (in delegate-mL, as specified in the BOM line)
        self.assertAlmostEqual(
            raw_move.product_uom_qty,
            250.0,
            places=2,
            msg="BOM line qty 250 delegate-mL must appear in product_uom_qty",
        )

    def test_mo_raw_move_product_qty_in_base_uom(self):
        """MO raw move: product_qty (computed base UoM) == 0.0125 Unit.

        product_qty is the stored computed base-UoM quantity.
        250 delegate-mL × 0.00005 = 0.0125 Unit.
        """
        self._stock_in(1.0)
        mo = self._make_mo(1.0)
        mo.action_assign()
        raw_move = mo.move_raw_ids.filtered(lambda m: m.product_id == self.ink)
        self.assertEqual(len(raw_move), 1, "Expected one raw move for ink")
        # product_qty is the computed base-UoM quantity
        self.assertAlmostEqual(
            raw_move.product_qty,
            0.0125,
            places=5,
            msg="product_qty (base UoM) must be 250 × 0.00005 = 0.0125 Unit",
        )

    def test_mo_move_line_quantity_product_uom(self):
        """move_line.quantity_product_uom == 0.0125 for a move_line in delegate-mL.

        quantity_product_uom is computed as:
            product_uom_id._compute_quantity(quantity, product_id.uom_id)
        = delegate_ml._compute_quantity(250.0, uom_unit) = 0.0125 Unit.

        We create the move_line manually against the raw move to directly test
        the UoM conversion logic (Crit 4 / delegation correctness), independent
        of stock reservation quant availability.
        """
        self._stock_in(10.0)
        mo = self._make_mo(1.0)
        raw_move = mo.move_raw_ids.filtered(lambda m: m.product_id == self.ink)
        self.assertEqual(len(raw_move), 1)
        # Manually create a move_line in delegate-mL and check quantity_product_uom
        ml = self.env["stock.move.line"].create(
            {
                "move_id": raw_move.id,
                "product_id": self.ink.id,
                "product_uom_id": self.delegate_ml.id,
                "quantity": 250.0,
                "location_id": self.stock_location.id,
                "location_dest_id": raw_move.location_dest_id.id,
            }
        )
        self.assertAlmostEqual(
            ml.quantity_product_uom,
            0.0125,
            places=5,
            msg="move_line.quantity_product_uom must be 0.0125 Unit "
            "(250 delegate-mL × 0.00005)",
        )


class TestScopingAllowedUomIds(TestMrpIntegrationBase):
    """Crit 5 + refinement: allowed_uom_ids scoping and cross-tree guard on BOM lines."""

    def test_delegate_ml_in_bom_line_allowed_uom_ids(self):
        """The ink's delegate-mL appears in the BOM line's allowed_uom_ids."""
        bom_line = self.bom.bom_line_ids[0]
        self.assertIn(
            self.delegate_ml,
            bom_line.allowed_uom_ids,
            "Ink's delegate-mL must be in BOM line allowed_uom_ids",
        )

    def test_base_uom_in_bom_line_allowed_uom_ids(self):
        """The ink's base UoM (Unit) is in the BOM line's allowed_uom_ids."""
        bom_line = self.bom.bom_line_ids[0]
        self.assertIn(
            self.uom_unit,
            bom_line.allowed_uom_ids,
            "Base UoM (Unit) must also be in BOM line allowed_uom_ids",
        )

    def test_other_product_delegate_absent_from_ink_bom_line_allowed_uom_ids(self):
        """Product B's delegate-mL is NOT in the ink BOM line's allowed_uom_ids."""
        other_product = self.env["product.product"].create(
            {
                "name": "Other Ink Product (Scoping Test)",
                "type": "consu",
                "uom_id": self.uom_unit.id,
            }
        )
        other_factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": other_product.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 0.0001,  # different factor → different delegate
            }
        )
        other_delegate = other_factor.delegate_uom_id
        other_product.product_tmpl_id.write(
            {"uom_factor_ids": [(4, other_factor.id)]}
        )
        bom_line = self.bom.bom_line_ids[0]
        self.assertNotIn(
            other_delegate,
            bom_line.allowed_uom_ids,
            "Other product's delegate-mL must NOT appear in ink BOM line allowed_uom_ids",
        )

    def test_cross_tree_uom_on_bom_line_raises_validation_error(self):
        """Forcing the generic mL (cross-tree for Unit-base product) on a BOM line raises."""
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.line"].create(
                {
                    "bom_id": self.bom.id,
                    "product_id": self.ink.id,
                    "product_qty": 100.0,
                    "product_uom_id": self.uom_ml.id,  # generic mL, cross-tree for Unit
                }
            )

    def test_same_category_uom_on_bom_line_allowed(self):
        """A same-category UoM (mL for an L-base product) passes the constraint.

        Uses two different products (finished + component) to avoid the BOM cycle check.
        The key is that mL and L are in the same volume category: no ValidationError.
        """
        volume_finished = self.env["product.product"].create(
            {
                "name": "Volume Finished Product (Scoping Test)",
                "type": "consu",
                "uom_id": self.uom_liter.id,
            }
        )
        volume_component = self.env["product.product"].create(
            {
                "name": "Volume Component (Scoping Test)",
                "type": "consu",
                "uom_id": self.uom_liter.id,
            }
        )
        # mL is in the same category as L → no ValidationError
        bom_vol = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": volume_finished.product_tmpl_id.id,
                "product_qty": 1.0,
                "product_uom_id": self.uom_liter.id,
                "bom_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": volume_component.id,
                            "product_qty": 1000.0,
                            "product_uom_id": self.uom_ml.id,  # same category as L
                        },
                    )
                ],
            }
        )
        self.assertTrue(bom_vol.bom_line_ids)


class TestConversionBehavior(TestMrpIntegrationBase):
    """Crit 9 + 10: conversion behavior after guard removal.

    The strong cross-tree guard was removed (review blocker 1+2): it incorrectly
    raised UserError on legitimate core conversions (T-GT→Units, Units→m²,
    kg price→Units). Criterion 9's safety is now carried entirely by the scoping
    @api.constrains on line models (see TestScopingAllowedUoms.
    test_cross_tree_uom_on_bom_line_raises_validation_error).

    These tests verify:
    - Cross-tree conversions with the generic UoM return core's numeric result
      (no raise) — core behaviour restored.
    - Delegate (intra-tree) conversions still resolve correctly.
    - Intra-category conversions are unaffected.
    """

    def test_generic_cross_tree_compute_quantity_no_raise(self):
        """Generic mL._compute_quantity(qty, Unit) returns core's numeric result
        without raising. Core O19 behaviour: silent cross-tree math."""
        result = self.uom_ml._compute_quantity(250.0, self.uom_unit, round=False)
        self.assertIsInstance(result, float, "Cross-tree with no delegate: should return float, not raise")

    def test_generic_cross_tree_compute_price_no_raise(self):
        """Generic mL._compute_price(price, Unit) returns core's numeric result
        without raising."""
        result = self.uom_ml._compute_price(0.04, self.uom_unit)
        self.assertIsInstance(result, float, "Cross-tree price with no delegate: should return float, not raise")

    def test_delegate_intra_tree_compute_quantity_correct(self):
        """delegate-mL._compute_quantity(qty, Unit) resolves correctly via the
        delegate tree (same tree after grafting)."""
        result = self.delegate_ml._compute_quantity(250.0, self.uom_unit, round=False)
        self.assertAlmostEqual(
            result,
            0.0125,
            places=5,
            msg="250 delegate-mL × 0.00005 = 0.0125 Unit (native intra-tree conversion)",
        )

    def test_intra_category_conversion_unaffected(self):
        """mL._compute_quantity(qty, L) (same volume tree) resolves correctly."""
        result = self.uom_ml._compute_quantity(1000.0, self.uom_liter, round=False)
        self.assertAlmostEqual(
            result, 1.0, places=5, msg="1000 mL → 1 L (intra-category, no exception)"
        )


class TestEdgeCases(TestMrpIntegrationBase):
    """Edge cases: base-UoM change blocked, foreign==base rejected, factor persists, cascade."""

    def test_base_uom_change_blocked_with_factor(self):
        """Changing base UoM while a factor row exists raises ValidationError."""
        template = self.env["product.template"].create(
            {
                "name": "Edge Case Ink – UoM Change",
                "uom_id": self.uom_unit.id,
            }
        )
        self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 0.00005,
            }
        )
        with self.assertRaises(ValidationError):
            template.uom_id = self.uom_liter

    def test_foreign_uom_equals_base_rejected(self):
        """foreign_uom_id == product base UoM raises ValidationError."""
        template = self.env["product.template"].create(
            {
                "name": "Edge Case Ink – Foreign==Base",
                "uom_id": self.uom_unit.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["product.uom.factor"].create(
                {
                    "product_tmpl_id": template.id,
                    "foreign_uom_id": self.uom_unit.id,  # same as base → error
                    "factor": 1.0,
                }
            )

    def test_factor_persists_on_inventory_tab_save(self):
        """Factor added via template write and saved: uom_factor_ids and uom_ids retain it.

        Regression for the clone-swap bug where the factor disappeared on save.
        """
        template = self.env["product.template"].create(
            {
                "name": "Edge Case Ink – Persist",
                "uom_id": self.uom_unit.id,
            }
        )
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 0.00005,
            }
        )
        template.write({"uom_factor_ids": [(4, factor.id)]})
        template.invalidate_recordset()
        self.assertIn(
            factor,
            template.uom_factor_ids,
            "Factor must still be in uom_factor_ids after write/save",
        )
        self.assertIn(
            factor.delegate_uom_id,
            template.uom_ids,
            "Delegate must still be in uom_ids after write/save (additive sync)",
        )

    def test_deleting_factor_removes_delegate_uom(self):
        """Unlinking a factor row removes its delegate uom.uom (cascade)."""
        template = self.env["product.template"].create(
            {
                "name": "Edge Case Ink – Delete Cascade",
                "uom_id": self.uom_unit.id,
            }
        )
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 0.00005,
            }
        )
        delegate_id = factor.delegate_uom_id.id
        factor.unlink()
        remaining = self.env["uom.uom"].browse(delegate_id).exists()
        self.assertFalse(
            remaining,
            "Delegate uom.uom must be deleted when the factor row is unlinked",
        )


class TestRegressionIntraCategoryAndUC(TestMrpIntegrationBase):
    """Crit 10: intra-category conversions unaffected; UC1-UC3 core assertions hold."""

    def test_intra_category_ml_to_liter(self):
        """mL → L (same volume category) uses standard Odoo conversion."""
        result = self.uom_ml._compute_quantity(1000.0, self.uom_liter, round=False)
        self.assertAlmostEqual(
            result, 1.0, places=5, msg="1000 mL must be 1.0 L (intra-category)"
        )

    def test_intra_category_liter_to_ml(self):
        """L → mL (same category) reverse."""
        result = self.uom_liter._compute_quantity(2.5, self.uom_ml, round=False)
        self.assertAlmostEqual(
            result, 2500.0, places=2, msg="2.5 L must be 2500 mL (intra-category)"
        )

    def test_uc1_delegate_created_on_factor_create(self):
        """UC1 regression: creating a factor row creates a delegate uom with correct attrs."""
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": self.ink.product_tmpl_id.id,
                "foreign_uom_id": self.uom_liter.id,
                "factor": 0.05,
            }
        )
        self.assertTrue(factor.delegate_uom_id)
        self.assertEqual(factor.delegate_uom_id.relative_uom_id, self.uom_unit)
        self.assertAlmostEqual(factor.delegate_uom_id.relative_factor, 0.05, places=6)
        self.assertEqual(factor.delegate_uom_id.name, self.uom_liter.name)

    def test_uc2_delegate_conversion_correct(self):
        """UC2 regression: delegate-mL._compute_quantity to Unit uses correct factor."""
        result = self.delegate_ml._compute_quantity(
            20000.0, self.uom_unit, round=False
        )
        self.assertAlmostEqual(
            result, 1.0, places=5, msg="20000 delegate-mL × 0.00005 = 1.0 Unit"
        )

    def test_uc3_delegate_in_uom_ids_after_sync(self):
        """UC3 regression: delegate UoM is in product's uom_ids after write/sync."""
        self.assertIn(
            self.delegate_ml,
            self.ink.product_tmpl_id.uom_ids,
            "Delegate must be in ink template's uom_ids (additive sync)",
        )
