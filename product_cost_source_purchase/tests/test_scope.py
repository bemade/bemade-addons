# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: only this company's, this variant's, live purchases count.

ACCEPTANCE CRITERIA
1. A purchase in another company is ignored.
2. A cancelled purchase is ignored.
3. A purchase of another variant of the same template is ignored.
4. A salesperson with no Purchase access still gets the purchase evidence.
"""
from odoo import Command
from odoo.tests import new_test_user, tagged

from .common import PurchaseCostSourceCommon


@tagged("-at_install", "post_install")
class TestScope(PurchaseCostSourceCommon):
    def test_other_company_purchase_is_ignored(self):
        company_b = self.env["res.company"].create({"name": "Company B"})
        self._order(40.0, on=self._months_ago(1), company=company_b)
        self._order(14.0, state="draft", company=company_b)
        self.assertEqual(self._resolve(company=self.company).sources, [])

    def test_cancelled_purchase_is_ignored(self):
        self._order(40.0, on=self._months_ago(1), state="cancel")
        self.assertEqual(self._resolve().sources, [])

    def test_other_variant_purchase_is_ignored(self):
        attribute = self.env["product.attribute"].create(
            {"name": "Size", "value_ids": [Command.create({"name": "S"}), Command.create({"name": "L"})]}
        )
        template = self.env["product.template"].create(
            {
                "name": "Variant Component",
                "type": "consu",
                "is_storable": True,
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": attribute.id,
                            "value_ids": [Command.set(attribute.value_ids.ids)],
                        }
                    )
                ],
            }
        )
        small, large = template.product_variant_ids
        self._order(40.0, on=self._months_ago(1), product=large)
        self.assertEqual(self._resolve(product=small).sources, [])
        self.assertAlmostEqual(self._resolve(product=large).unit_cost, 40.0)

    def test_salesperson_without_purchase_access(self):
        self._order(40.0, on=self._months_ago(1))
        user = new_test_user(
            self.env, login="cost_seller", groups="sales_team.group_sale_salesman"
            if self.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)
            else "base.group_user",
        )
        self.assertFalse(user.has_group("purchase.group_purchase_user"))
        product = self.product.with_user(user)
        self.assertAlmostEqual(product._resolve_cost().unit_cost, 40.0)
