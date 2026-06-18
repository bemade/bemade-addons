"""
Test UC2: Cross-Category Quantity and Price Conversion (Delegation Design)

As a salesperson or purchaser, I want quantity and price conversions between
UoMs of different categories (e.g. mL to g) to use the product-specific
conversion factor so that when I sell or purchase in a cross-category UoM,
the resulting quantities and prices are correct.

In the v4 delegation design, product.uom.factor creates a delegate uom.uom
whose relative_uom_id = product's base UoM and relative_factor = factor.
The delegate is added to the product's uom_ids so core _compute_quantity and
_compute_price resolve it natively without any product_id context injection.

Acceptance Criteria:
- With the delegate UoM selected (not the generic mL), converting to the
  product's base UoM uses the cross-category factor natively
- The delegate's relative_factor drives the conversion
- Two products with different factors produce different delegates and results
- Cross-tree conversions using the generic (non-delegate) UoM return core's
  numeric result without raising — the strong guard has been removed (review
  blocker 1+2). Safety is enforced instead by the scoping @api.constrains on
  line models (ValidationError on wrong cross-tree selection at save time).
- price _compute_price also returns core's numeric result for cross-tree pairs
"""

from odoo.tests.common import TransactionCase


class TestUC2CrossCategoryConversion(TransactionCase):
    """Test UC2: Cross-Category Quantity and Price Conversion"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_gram = cls.env.ref("uom.product_uom_gram")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")

        cls.product_cyan = cls.env["product.product"].create(
            {
                "name": "Ink - Cyan",
                "uom_id": cls.uom_gram.id,
            }
        )
        # Specific gravity 1.05: 1 mL-delegate = 1.05 g
        cls.factor_cyan = cls.env["product.uom.factor"].create(
            {
                "product_tmpl_id": cls.product_cyan.product_tmpl_id.id,
                "foreign_uom_id": cls.uom_ml.id,
                "factor": 1.05,
            }
        )
        # The delegate_uom_id IS the product-specific mL for cyan ink
        cls.delegate_ml_cyan = cls.factor_cyan.delegate_uom_id

    def test_delegate_to_base_conversion(self):
        """Converting via the delegate UoM (product-specific mL-for-cyan)
        to the base UoM (g) should use the cross-category factor natively.
        500 mL-delegate * relative_factor(1.05) should yield 525 g."""
        result = self.delegate_ml_cyan._compute_quantity(
            500, self.uom_gram, round=False
        )
        self.assertAlmostEqual(
            result,
            525.0,
            places=2,
            msg="500 product-specific mL (SG 1.05) should be 525 g",
        )

    def test_base_to_delegate_conversion(self):
        """Converting from base UoM (g) to the delegate UoM (product-specific mL)
        should use the inverse of the cross-category factor.
        525 g / relative_factor(1.05) should yield 500 mL-delegate."""
        result = self.uom_gram._compute_quantity(
            525, self.delegate_ml_cyan, round=False
        )
        self.assertAlmostEqual(
            result,
            500.0,
            places=2,
            msg="525 g should be 500 product-specific mL (SG 1.05)",
        )

    def test_different_products_different_delegates(self):
        """Two products with different densities should have different delegates
        and produce different conversion results for the same quantity."""
        product_magenta = self.env["product.product"].create(
            {
                "name": "Ink - Magenta",
                "uom_id": self.uom_gram.id,
            }
        )
        factor_magenta = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": product_magenta.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.10,
            }
        )
        delegate_ml_magenta = factor_magenta.delegate_uom_id

        cyan_result = self.delegate_ml_cyan._compute_quantity(
            500, self.uom_gram, round=False
        )
        magenta_result = delegate_ml_magenta._compute_quantity(
            500, self.uom_gram, round=False
        )
        self.assertAlmostEqual(cyan_result, 525.0, places=2)
        self.assertAlmostEqual(magenta_result, 550.0, places=2)
        self.assertNotAlmostEqual(
            cyan_result,
            magenta_result,
            places=2,
            msg="Different densities should produce different results",
        )

    def test_same_category_conversion_unaffected(self):
        """Same-category conversions (g to kg) should use standard UoM
        factors and not be affected by the cross-category factor."""
        uom_kg = self.env.ref("uom.product_uom_kgm")
        result = self.uom_gram._compute_quantity(1000, uom_kg, round=False)
        self.assertAlmostEqual(
            result,
            1.0,
            places=5,
            msg="1000 g should be 1 kg regardless of cross-category factor",
        )

    def test_generic_uom_cross_tree_no_raise(self):
        """Using the generic mL (not the product's delegate) to convert to g
        returns core's numeric result without raising. The strong conversion-time
        guard was removed (review blocker 1+2): wrong UoM selection is blocked
        instead by the scoping @api.constrains on line models (ValidationError
        at save). Core's cross-tree math falls through silently here."""
        result = self.uom_ml._compute_quantity(500, self.uom_gram, round=False)
        self.assertIsInstance(result, float, "Cross-tree with no delegate: should return float, not raise")

    def test_price_delegate_to_base(self):
        """Price per mL-delegate converted to price per g should account for
        density. $0.105/mL-delegate / relative_factor(1.05) = $0.10/g."""
        result = self.delegate_ml_cyan._compute_price(0.105, self.uom_gram)
        self.assertAlmostEqual(
            result,
            0.10,
            places=5,
            msg="$0.105/mL-delegate should be $0.10/g for ink with SG 1.05",
        )

    def test_price_base_to_delegate(self):
        """Price per g converted to price per mL-delegate should account for
        density. $0.10/g * relative_factor(1.05) = $0.105/mL-delegate."""
        result = self.uom_gram._compute_price(0.10, self.delegate_ml_cyan)
        self.assertAlmostEqual(
            result,
            0.105,
            places=5,
            msg="$0.10/g should be $0.105/mL-delegate for ink with SG 1.05",
        )

    def test_price_same_category_unaffected(self):
        """Same-category price conversions (g to kg) should use standard UoM
        factors and not be affected by the cross-category factor."""
        uom_kg = self.env.ref("uom.product_uom_kgm")
        result = self.uom_gram._compute_price(0.10, uom_kg)
        self.assertAlmostEqual(
            result,
            100.0,
            places=5,
            msg="$0.10/g should be $100/kg regardless of cross-category factor",
        )

    def test_price_generic_cross_tree_no_raise(self):
        """_compute_price on a genuinely cross-tree pair (generic mL → g) returns
        core's numeric result without raising. The strong guard was removed (review
        blocker 1+2); wrong UoM selection is blocked by the scoping @api.constrains
        at save time instead."""
        result = self.uom_ml._compute_price(0.105, self.uom_gram)
        self.assertIsInstance(result, float, "Cross-tree price: should return float, not raise")

    def test_compute_quantity_same_uom(self):
        """Converting a UoM to itself should return the original qty."""
        result = self.delegate_ml_cyan._compute_quantity(
            500, self.delegate_ml_cyan, round=False
        )
        self.assertAlmostEqual(result, 500.0, places=2)

    def test_compute_price_same_uom(self):
        """Converting a price to the same UoM should return the original."""
        result = self.delegate_ml_cyan._compute_price(10.0, self.delegate_ml_cyan)
        self.assertAlmostEqual(result, 10.0, places=2)

    def test_is_product_factor_computed(self):
        """is_product_factor should be True for the delegate UoM and False for
        the generic mL."""
        self.assertTrue(
            self.delegate_ml_cyan.is_product_factor,
            "Delegate UoM should have is_product_factor=True",
        )
        self.assertFalse(
            self.uom_ml.is_product_factor,
            "Generic mL should have is_product_factor=False",
        )

    def test_is_product_factor_search(self):
        """is_product_factor domain search should find delegate UoMs."""
        delegates = self.env["uom.uom"].search([("is_product_factor", "=", True)])
        self.assertIn(
            self.delegate_ml_cyan,
            delegates,
            "Delegate UoM should appear in is_product_factor=True search",
        )
        self.assertNotIn(
            self.uom_ml,
            delegates,
            "Generic mL should not appear in is_product_factor=True search",
        )
