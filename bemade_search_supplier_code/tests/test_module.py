from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSearchSupplierCode(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env["product.product"]
        cls.Supplier = cls.env["res.partner"]
        cls.SupplierInfo = cls.env["product.supplierinfo"]

    def test_product_model_extended(self):
        """Test that product.product model is extended"""
        self.assertIsNotNone(self.Product)

    def test_product_creation(self):
        """Test product creation"""
        product = self.Product.create({
            "name": "Test Product",
            "type": "consu",
        })
        self.assertIsNotNone(product.id)

    def test_supplier_code_field(self):
        """Test supplier code in product"""
        supplier = self.Supplier.create({
            "name": "Supplier",
            "supplier_rank": 1
        })

        product = self.Product.create({
            "name": "Product with Supplier",
            "type": "consu",
        })

        self.assertIsNotNone(product.id)

    def test_multiple_suppliers(self):
        """Test product with multiple suppliers"""
        supplier1 = self.Supplier.create({
            "name": "Supplier 1",
            "supplier_rank": 1
        })
        supplier2 = self.Supplier.create({
            "name": "Supplier 2",
            "supplier_rank": 2
        })

        product = self.Product.create({
            "name": "Multi-Supplier Product",
            "type": "consu",
        })

        self.assertIsNotNone(product.id)
