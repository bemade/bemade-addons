"""
Test UC1: Product-Specific Cross-Category Conversion Factor (Delegation Design)

As a product manager, I want to define a conversion factor on a product's
foreign UoM so that the system can correctly convert between UoMs of
different categories (e.g. volume to weight) for that specific product.

The v4 design delegates via _inherits = {'uom.uom': 'delegate_uom_id'}.
Each product.uom.factor row IS a uom.uom (the delegate) whose:
  - relative_uom_id = product's base UoM
  - relative_factor = the cross-category factor
  - name = foreign_uom_id.name

Acceptance Criteria:
- A factor field exists on product.uom.factor and defaults to 1.0
- The factor can store a custom value (e.g. 1.05 for specific gravity)
- Creating a factor row auto-creates a delegate uom.uom with the correct
  relative_uom_id, relative_factor, and name
- The delegate_uom_id.relative_factor is updated when factor is changed
- The foreign unit (foreign_uom_id) cannot be the product's base UoM itself
- The foreign unit cannot be in the same category as the product's base UoM
  (intra-category conversion is handled by core; cross-category delegation only)
- A product.uom.factor record is linked to a product.template via
  product_tmpl_id, with an optional product_ids M2M to restrict to specific
  variants (empty = applies to all variants)
- All product_ids must belong to the same product_tmpl_id
- A variant can only appear on one product.uom.factor per foreign_uom_id
- The delegate UoM is added to the product's uom_ids (additive sync only)
- Blocking base UoM change while factor rows exist
"""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestUC1ProductUomFactor(TransactionCase):
    """Test UC1: Product-Specific Cross-Category Conversion Factor"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_gram = cls.env.ref("uom.product_uom_gram")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Ink - Cyan",
                "uom_id": cls.uom_gram.id,
            }
        )

    def test_factor_field_exists_with_default(self):
        """The factor field should exist on product.uom.factor and default to 1.0."""
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
            }
        )
        self.assertEqual(factor.factor, 1.0, "The factor field should default to 1.0")

    def test_delegate_uom_created_on_factor_create(self):
        """Creating a factor row should auto-create a delegate uom.uom."""
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.05,
            }
        )
        self.assertTrue(factor.delegate_uom_id, "Delegate uom.uom should be created")
        self.assertEqual(
            factor.delegate_uom_id.relative_uom_id,
            self.product.uom_id,
            "Delegate relative_uom_id should be the product's base UoM",
        )
        self.assertAlmostEqual(
            factor.delegate_uom_id.relative_factor,
            1.05,
            places=5,
            msg="Delegate relative_factor should match the factor value",
        )
        self.assertEqual(
            factor.delegate_uom_id.name,
            self.uom_ml.name,
            "Delegate name should match the foreign UoM name",
        )

    def test_factor_write_updates_delegate(self):
        """Changing the factor field should update the delegate's relative_factor."""
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.05,
            }
        )
        factor.factor = 1.10
        self.assertAlmostEqual(
            factor.delegate_uom_id.relative_factor,
            1.10,
            places=5,
            msg="Delegate relative_factor should be updated when factor changes",
        )

    def test_delegate_added_to_product_uom_ids(self):
        """The delegate UoM should be in the product template's uom_ids after sync."""
        template = self.product.product_tmpl_id
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.05,
            }
        )
        # Trigger sync
        template.write({"uom_factor_ids": [(4, factor.id)]})
        self.assertIn(
            factor.delegate_uom_id,
            template.uom_ids,
            "Delegate UoM should be added to template uom_ids",
        )

    def test_base_uom_as_foreign_rejected(self):
        """Setting the base UoM as the foreign UoM should raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["product.uom.factor"].create(
                {
                    "product_tmpl_id": self.product.product_tmpl_id.id,
                    "foreign_uom_id": self.uom_gram.id,  # same as base UoM
                    "factor": 1.0,
                }
            )

    def test_same_category_foreign_uom_rejected(self):
        """A foreign UoM in the same category as the base UoM should raise."""
        uom_kg = self.env.ref("uom.product_uom_kgm")
        with self.assertRaises(ValidationError):
            self.env["product.uom.factor"].create(
                {
                    "product_tmpl_id": self.product.product_tmpl_id.id,
                    "foreign_uom_id": uom_kg.id,
                    "factor": 1000.0,
                }
            )

    def test_product_ids_must_belong_to_same_template(self):
        """Assigning a variant from a different template should raise."""
        other_product = self.env["product.product"].create(
            {"name": "Other Product", "uom_id": self.uom_gram.id}
        )
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": self.product.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
            }
        )
        with self.assertRaises(ValidationError):
            factor.product_ids = [(4, other_product.id)]

    def test_no_duplicate_factors_same_foreign_uom(self):
        """Two factor records with the same (template, foreign_uom, product_ids)
        should not both persist — the duplicate is removed."""
        template = self.product.product_tmpl_id
        # Creating two identical catch-alls; the second should trigger cleanup
        self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.05,
            }
        )
        self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.10,
            }
        )
        remaining = self.env["product.uom.factor"].search(
            [
                ("product_tmpl_id", "=", template.id),
                ("foreign_uom_id", "=", self.uom_ml.id),
                ("product_ids", "=", False),
            ]
        )
        self.assertEqual(
            len(remaining),
            1,
            "Duplicate catch-all factor rows should be auto-cleaned",
        )

    def test_base_uom_change_blocked_with_factors(self):
        """Changing the product's base UoM while factor rows exist should raise."""
        uom_liter = self.env.ref("uom.product_uom_litre")
        template = self.env["product.template"].create(
            {
                "name": "Test Ink for Block Test",
                "uom_id": self.uom_gram.id,
            }
        )
        self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.05,
            }
        )
        with self.assertRaises(ValidationError):
            template.uom_id = uom_liter
