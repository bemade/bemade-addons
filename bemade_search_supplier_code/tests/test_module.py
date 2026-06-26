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

    def test_compute_supplier_codes_single(self):
        """Compute concatenates the supplier code of a single seller."""
        supplier = self.Supplier.create({
            "name": "ACME", "supplier_rank": 1,
        })
        product = self.Product.create({
            "name": "Coded Product", "type": "consu",
        })
        self.SupplierInfo.create({
            "partner_id": supplier.id,
            "product_id": product.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_code": "ACME-001",
        })
        # Ensure the seller is attached to the variant the compute reads.
        self.assertIn(
            product.id, self.SupplierInfo.search(
                [("product_id", "=", product.id)]).mapped("product_id.id"),
        )
        product.invalidate_recordset(["supplier_codes"])
        self.assertEqual(product.supplier_codes, "ACME-001")

    def test_compute_supplier_codes_multiple_and_false(self):
        """Compute joins multiple codes and drops False (non-str) codes."""
        supplier1 = self.Supplier.create({"name": "S1", "supplier_rank": 1})
        supplier2 = self.Supplier.create({"name": "S2", "supplier_rank": 1})
        supplier3 = self.Supplier.create({"name": "S3", "supplier_rank": 1})
        product = self.Product.create({
            "name": "Multi Coded", "type": "consu",
        })
        tmpl = product.product_tmpl_id.id
        self.SupplierInfo.create({
            "partner_id": supplier1.id, "product_id": product.id,
            "product_tmpl_id": tmpl, "product_code": "AAA",
        })
        self.SupplierInfo.create({
            "partner_id": supplier2.id, "product_id": product.id,
            "product_tmpl_id": tmpl, "product_code": "BBB",
        })
        # A seller without a product_code -> product_code is False (non-str),
        # exercising the isinstance(x, str) filter branch.
        self.SupplierInfo.create({
            "partner_id": supplier3.id, "product_id": product.id,
            "product_tmpl_id": tmpl,
        })
        product.invalidate_recordset(["supplier_codes"])
        codes = product.supplier_codes
        self.assertIn("AAA", codes)
        self.assertIn("BBB", codes)
        # The False code must not appear (e.g. no "False" / no empty token).
        self.assertNotIn("False", codes)
        self.assertEqual(
            sorted(c.strip() for c in codes.split(",")), ["AAA", "BBB"],
        )

    def test_search_supplier_codes_match(self):
        """Searching supplier_codes returns the product with that code."""
        supplier = self.Supplier.create({"name": "SrchSup", "supplier_rank": 1})
        product = self.Product.create({
            "name": "Searchable", "type": "consu",
        })
        self.SupplierInfo.create({
            "partner_id": supplier.id, "product_id": product.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_code": "UNIQUE-CODE-XYZ",
        })
        found = self.Product.search([("supplier_codes", "=", "UNIQUE-CODE-XYZ")])
        self.assertIn(product, found)

    def test_search_supplier_codes_like(self):
        """Search supports operators other than equality (ilike)."""
        supplier = self.Supplier.create({"name": "LikeSup", "supplier_rank": 1})
        product = self.Product.create({
            "name": "Likeable", "type": "consu",
        })
        self.SupplierInfo.create({
            "partner_id": supplier.id, "product_id": product.id,
            "product_tmpl_id": product.product_tmpl_id.id,
            "product_code": "PREFIX-12345",
        })
        found = self.Product.search([("supplier_codes", "ilike", "prefix-12")])
        self.assertIn(product, found)

    def test_search_supplier_codes_empty_value(self):
        """Empty search value short-circuits to an empty domain (no filtering)."""
        # Directly exercise the `if not value: return []` branch: a falsy value
        # must yield an empty (match-all) domain leaf.
        domain = self.Product._search_supplier_codes("=", False)
        self.assertEqual(domain, [])
        # Through the ORM: searching on a falsy value must not raise.
        self.Product.search([("supplier_codes", "=", False)])
