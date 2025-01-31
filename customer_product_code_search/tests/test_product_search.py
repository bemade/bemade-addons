from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCustomerProductCodeSearch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test partners
        cls.partner1 = cls.env["res.partner"].create(
            {
                "name": "Test Partner 1",
            }
        )
        cls.partner2 = cls.env["res.partner"].create(
            {
                "name": "Test Partner 2",
            }
        )

        # Create test products
        cls.product1 = cls.env["product.product"].create(
            {
                "name": "Test Product 1",
                "type": "consu",
                "default_code": "TEST001",
            }
        )
        cls.product2 = cls.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "consu",
                "default_code": "TEST002",
            }
        )

        # Create customer product codes
        cls.customer_code1 = cls.env["product.customer.code"].create(
            {
                "product_id": cls.product1.product_tmpl_id.id,
                "partner_id": cls.partner1.id,
                "product_code": "CUST001",
                "product_name": "Customer 1 Product Name",
            }
        )
        cls.customer_code2 = cls.env["product.customer.code"].create(
            {
                "product_id": cls.product2.product_tmpl_id.id,
                "partner_id": cls.partner2.id,
                "product_code": "CUST002",
                "product_name": "Customer 2 Product Name",
            }
        )

    def test_search_by_customer_code_with_partner(self):
        """Test searching products by customer code with partner context"""
        # Search with partner1 context
        products = (
            self.env["product.product"]
            .with_context(partner_id=self.partner1.id)
            .search([("display_name", "ilike", "CUST")])
        )
        self.assertIn(
            self.product1,
            products,
            "Should find product1 when searching by customer code with partner1 context",
        )
        self.assertNotIn(
            self.product2,
            products,
            "Should not find product2 when searching with partner1 context",
        )

    def test_search_by_customer_code_without_partner(self):
        """Test searching products by customer code without partner context"""
        # Search without partner context should find both products
        products = self.env["product.product"].search(
            [("display_name", "ilike", "CUST")]
        )
        self.assertIn(
            self.product1,
            products,
            "Should find product1 when searching by customer code without partner context",
        )
        self.assertIn(
            self.product2,
            products,
            "Should find product2 when searching by customer code without partner context",
        )

        # Search for specific customer code
        products = self.env["product.product"].search(
            [("display_name", "ilike", "CUST002")]
        )
        self.assertIn(
            self.product2,
            products,
            "Should find product2 when searching by its specific customer code without partner context",
        )
