"""Use case: product templates are listed by internal reference.

Acceptance criteria
-------------------
1. Product templates are ordered by internal reference, then name (favourites
   first, as in standard Odoo).
2. In the product list, the internal reference column comes before the name.
"""

from lxml import etree

from .common import CustomerProductCodeCase


class TestProductTemplateList(CustomerProductCodeCase):
    def test_template_order(self):
        """AC1"""
        b = self._create_product("Alpha", "B-1").product_tmpl_id
        a2 = self._create_product("Zulu", "A-1").product_tmpl_id
        a1 = self._create_product("Yankee", "A-1").product_tmpl_id
        found = self.env["product.template"].search([("id", "in", (a1 | a2 | b).ids)])
        self.assertEqual(found, a1 | a2 | b)
        self.assertEqual(found.ids, [a1.id, a2.id, b.id])

    def test_reference_column_first(self):
        """AC2"""
        arch = self.env["product.template"].get_view(
            self.env.ref("product.product_template_tree_view").id, "list"
        )["arch"]
        names = [f.get("name") for f in etree.fromstring(arch).iter("field")]
        self.assertLess(names.index("default_code"), names.index("name"))
