"""
Test UC3: Cross-Category UoM Conversion Factors on Product Form (Delegation Design)

As a product manager, I want to configure conversion factors for cross-category
UoMs on the product form, and have the delegated UoM automatically included in
the product's allowed UoMs so that order lines can select it.

In the v4 delegation design:
  - factor rows are created manually (no auto-create from uom_ids)
  - each factor row creates a delegate uom.uom linked via delegate_uom_id
  - the delegate is added (additive only) to the template's uom_ids by _sync_factor_uom_ids
  - the foreign_uom_id column (renamed from uom_id) is shown in the view

Acceptance Criteria:
- The product template form has a "Unit Conversions" section showing
  uom_factor_ids with foreign_uom_id (readonly), product_ids, and factor
- Creating a factor record shows the delegate in the product's uom_ids
- The factor field is editable and updating it syncs to delegate_uom_id
- The product variant form shows applicable factor rows via uom_factor_ids
"""

from odoo.tests import Form
from odoo.tests.common import TransactionCase


class TestUC3ProductUomFactorView(TransactionCase):
    """Test UC3: Cross-Category UoM Conversion Factors on Product Form"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.config.settings"].create({"group_uom": True}).execute()
        cls.uom_gram = cls.env.ref("uom.product_uom_gram")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")

    def test_delegate_in_product_uom_ids_after_sync(self):
        """After creating a factor row and triggering _sync_factor_uom_ids,
        the delegate UoM should appear in the template's uom_ids."""
        template = self.env["product.template"].create(
            {
                "name": "Test Ink",
                "uom_id": self.uom_gram.id,
            }
        )
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
            "Delegate UoM should be in product template's uom_ids after sync",
        )

    def test_factor_editable_on_template_form(self):
        """When a factor row exists, its factor value can be edited on the
        template form and the change propagates to the delegate."""
        template = self.env["product.template"].create(
            {
                "name": "Test Ink",
                "uom_id": self.uom_gram.id,
            }
        )
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.00,
            }
        )

        form = Form(template, view="product.product_template_only_form_view")
        with form.uom_factor_ids.edit(0) as line:
            line.factor = 1.05
        template = form.save()

        puom = template.uom_factor_ids.filtered(
            lambda r: r.foreign_uom_id == self.uom_ml
        )
        self.assertEqual(len(puom), 1)
        self.assertAlmostEqual(
            puom.factor,
            1.05,
            places=5,
            msg="Factor should be editable via the product template form",
        )
        self.assertAlmostEqual(
            puom.delegate_uom_id.relative_factor,
            1.05,
            places=5,
            msg="Delegate relative_factor should be updated after form save",
        )

    def test_variant_uom_factor_ids_shows_applicable_factors(self):
        """The computed uom_factor_ids on product.product should return
        only factors that apply to this variant: catch-all lines (no
        product_ids) and lines where this variant is in product_ids."""
        attr = self.env["product.attribute"].create({"name": "Color"})
        val_red = self.env["product.attribute.value"].create(
            {"name": "Red", "attribute_id": attr.id}
        )
        val_blue = self.env["product.attribute.value"].create(
            {"name": "Blue", "attribute_id": attr.id}
        )
        template = self.env["product.template"].create(
            {
                "name": "Test Ink",
                "uom_id": self.uom_gram.id,
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attr.id,
                            "value_ids": [(6, 0, [val_red.id, val_blue.id])],
                        },
                    )
                ],
            }
        )
        variant_red, variant_blue = template.product_variant_ids

        # Create a catch-all factor (no product_ids)
        catchall = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 1.05,
            }
        )

        # Both variants see the catch-all
        self.assertIn(catchall, variant_red.uom_factor_ids)
        self.assertIn(catchall, variant_blue.uom_factor_ids)

        # Create a red-specific factor row (discriminated by product_ids)
        red_factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": template.id,
                "foreign_uom_id": self.uom_ml.id,
                "product_ids": [(4, variant_red.id)],
                "factor": 1.10,
            }
        )
        template.invalidate_recordset(["uom_factor_ids"])
        variant_red.invalidate_recordset(["uom_factor_ids"])
        variant_blue.invalidate_recordset(["uom_factor_ids"])

        # Red sees both the catch-all and its discriminated line
        self.assertIn(catchall, variant_red.uom_factor_ids)
        self.assertIn(red_factor, variant_red.uom_factor_ids)
        # Blue sees only the catch-all
        self.assertIn(catchall, variant_blue.uom_factor_ids)
        self.assertNotIn(red_factor, variant_blue.uom_factor_ids)

    def test_new_product_uom_factor_ids_empty(self):
        """A new (unsaved) product should return empty uom_factor_ids."""
        new_product = self.env["product.product"].new({"name": "Unsaved"})
        self.assertFalse(new_product.uom_factor_ids)
