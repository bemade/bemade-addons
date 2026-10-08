"""Use case: who can see and manage customer codes.

Acceptance criteria
-------------------
1. An internal user without sales rights can read codes but not create, edit or
   delete them.
2. A salesperson can create, edit and delete codes.
3. The *Customer Product Codes* menu is visible to the manager group only.
4. A code on a shared product is visible in every company; a code on a product
   restricted to a company is not visible to a user outside that company.
"""

from odoo.exceptions import AccessError
from odoo.tests import new_test_user

from .common import CustomerProductCodeCase


class TestSecurity(CustomerProductCodeCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, "cpc_user", groups="base.group_user")
        cls.salesman = new_test_user(
            cls.env, "cpc_salesman", groups="sales_team.group_sale_salesman"
        )

    def _vals(self):
        return {
            "partner_id": self.contact.id,
            "product_id": self.template.id,
            "product_code": "NEW",
        }

    def test_internal_user_read_only(self):
        """AC1"""
        Code = self.env["product.customer.code"].with_user(self.user)
        self.assertEqual(Code.browse(self.code.id).product_code, "CUST-1")
        with self.assertRaises(AccessError):
            Code.create(self._vals())
        with self.assertRaises(AccessError):
            Code.browse(self.code.id).write({"product_code": "X"})
        with self.assertRaises(AccessError):
            Code.browse(self.code.id).unlink()

    def test_salesman_can_manage(self):
        """AC2"""
        Code = self.env["product.customer.code"].with_user(self.salesman)
        code = Code.create(self._vals())
        code.product_code = "NEWER"
        code.unlink()
        self.assertFalse(code.exists())

    def test_menu_restricted_to_manager_group(self):
        """AC3"""
        menu = self.env.ref("customer_product_code.menu_product_customer_code")
        Menu = self.env["ir.ui.menu"]
        self.assertNotIn(menu.id, Menu.with_user(self.salesman)._visible_menu_ids())
        self.salesman.group_ids += self.env.ref(
            "customer_product_code.group_product_customer_code_manager"
        )
        self.env.registry.clear_cache()
        self.assertIn(menu.id, Menu.with_user(self.salesman)._visible_menu_ids())

    def test_multi_company_rule(self):
        """AC4"""
        other_company = self.env["res.company"].create({"name": "Other Co"})
        restricted = self._create_product("Secret", "SEC-1")
        restricted.company_id = other_company
        secret = self._add_code(self.customer, restricted, "SECRET")
        Code = self.env["product.customer.code"].with_user(self.salesman)
        visible = Code.search([("partner_id", "=", self.customer.id)])
        self.assertIn(self.code, visible)
        self.assertNotIn(secret, visible)
