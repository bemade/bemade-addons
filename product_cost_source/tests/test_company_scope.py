# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: the last-known-price fallback respects company and variant.

ACCEPTANCE CRITERIA
1. A supplier price restricted to another company is never offered as the
   last known price.
2. A supplier price restricted to another variant is never offered for this
   one.
3. The price-age setting refuses zero and negative values.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestCompanyScope(ProductCostSourceCommon):
    def test_other_company_price_is_not_the_fallback(self):
        company_b = self.env["res.company"].create({"name": "Company B"})
        self._supplier_price(
            10.0, company_id=company_b.id, date_start=self._months_ago(2)
        )
        resolution = self._resolve(company=self.company)
        self.assertEqual(resolution.sources, [])
        self.assertEqual(resolution.confidence, "unknown")

    def test_other_company_price_does_not_outrank_own_price(self):
        company_b = self.env["res.company"].create({"name": "Company B"})
        self._supplier_price(
            10.0, company_id=company_b.id, date_start=self._months_ago(2)
        )
        own = self._supplier_price(20.0, company_id=self.company.id)
        resolution = self._resolve(company=self.company)
        self.assertEqual(len(resolution.sources), 1)
        self.assertAlmostEqual(resolution.unit_cost, 20.0)
        self.assertIsNone(resolution.sources[0].priced_on)
        self.assertTrue(own)

    def test_other_variant_price_is_not_the_fallback(self):
        template = self.product.product_tmpl_id
        attribute = self.env["product.attribute"].create(
            {
                "name": "Size",
                "value_ids": [
                    (0, 0, {"name": "S"}),
                    (0, 0, {"name": "L"}),
                ],
            }
        )
        template.write(
            {
                "attribute_line_ids": [
                    (
                        0,
                        0,
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [(6, 0, attribute.value_ids.ids)],
                        },
                    )
                ]
            }
        )
        variant_1, variant_2 = template.product_variant_ids
        self.assertNotEqual(variant_1, variant_2)
        self._supplier_price(
            10.0, product=variant_2, date_start=self._months_ago(2)
        ).write({"product_id": variant_2.id})
        self.assertEqual(self._resolve(product=variant_1).sources, [])
        self.assertEqual(len(self._resolve(product=variant_2).sources), 1)

    def test_price_age_setting_refuses_non_positive_values(self):
        for value in (0, -1):
            with self.assertRaises(ValidationError):
                self.env["res.config.settings"].create({"price_age_months": value})
