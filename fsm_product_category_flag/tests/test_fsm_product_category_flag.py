from odoo.tests.common import TransactionCase


class TestFsmProductCategoryFlag(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ProductCategory = self.env['product.category']

    def test_module_installed(self):
        """Test that the module is properly installed"""
        # Verify that the is_fsm_product field exists on product.category
        self.assertTrue(
            hasattr(self.env['product.category'], '_fields'),
            "product.category model should have fields"
        )
        self.assertIn(
            'is_fsm_product',
            self.env['product.category']._fields,
            "is_fsm_product field should be present on product.category"
        )

    def test_create_fsm_category_enabled(self):
        """Test creating a product category with is_fsm_product=True"""
        category = self.ProductCategory.create({
            'name': 'FSM Services',
            'is_fsm_product': True,
        })

        self.assertTrue(category.is_fsm_product)
        self.assertEqual(category.name, 'FSM Services')

    def test_create_fsm_category_disabled(self):
        """Test creating a product category with is_fsm_product=False"""
        category = self.ProductCategory.create({
            'name': 'Regular Products',
            'is_fsm_product': False,
        })

        self.assertFalse(category.is_fsm_product)
        self.assertEqual(category.name, 'Regular Products')

    def test_default_is_fsm_product_false(self):
        """Test that is_fsm_product defaults to False when not specified"""
        category = self.ProductCategory.create({
            'name': 'Default Category',
        })

        self.assertFalse(
            category.is_fsm_product,
            "is_fsm_product should default to False"
        )

    def test_update_fsm_product_flag_true_to_false(self):
        """Test updating is_fsm_product from True to False"""
        category = self.ProductCategory.create({
            'name': 'Updatable Category',
            'is_fsm_product': True,
        })

        self.assertTrue(category.is_fsm_product)

        category.is_fsm_product = False
        self.assertFalse(category.is_fsm_product)

    def test_update_fsm_product_flag_false_to_true(self):
        """Test updating is_fsm_product from False to True"""
        category = self.ProductCategory.create({
            'name': 'Non-FSM Category',
            'is_fsm_product': False,
        })

        self.assertFalse(category.is_fsm_product)

        category.is_fsm_product = True
        self.assertTrue(category.is_fsm_product)

    def test_multiple_fsm_categories(self):
        """Test creating multiple categories with mixed FSM flags"""
        fsm_cat = self.ProductCategory.create({
            'name': 'FSM Category 1',
            'is_fsm_product': True,
        })
        non_fsm_cat = self.ProductCategory.create({
            'name': 'Non-FSM Category 1',
            'is_fsm_product': False,
        })
        another_fsm_cat = self.ProductCategory.create({
            'name': 'FSM Category 2',
            'is_fsm_product': True,
        })

        self.assertTrue(fsm_cat.is_fsm_product)
        self.assertFalse(non_fsm_cat.is_fsm_product)
        self.assertTrue(another_fsm_cat.is_fsm_product)

    def test_search_fsm_categories(self):
        """Test searching for FSM product categories"""
        fsm_cat1 = self.ProductCategory.create({
            'name': 'FSM Category A',
            'is_fsm_product': True,
        })
        non_fsm_cat = self.ProductCategory.create({
            'name': 'Non-FSM Category A',
            'is_fsm_product': False,
        })
        fsm_cat2 = self.ProductCategory.create({
            'name': 'FSM Category B',
            'is_fsm_product': True,
        })

        fsm_categories = self.ProductCategory.search([
            ('is_fsm_product', '=', True)
        ])

        self.assertIn(fsm_cat1, fsm_categories)
        self.assertNotIn(non_fsm_cat, fsm_categories)
        self.assertIn(fsm_cat2, fsm_categories)

    def test_search_non_fsm_categories(self):
        """Test searching for non-FSM product categories"""
        fsm_cat = self.ProductCategory.create({
            'name': 'FSM Category',
            'is_fsm_product': True,
        })
        non_fsm_cat1 = self.ProductCategory.create({
            'name': 'Non-FSM Category 1',
            'is_fsm_product': False,
        })
        non_fsm_cat2 = self.ProductCategory.create({
            'name': 'Non-FSM Category 2',
            'is_fsm_product': False,
        })

        non_fsm_categories = self.ProductCategory.search([
            ('is_fsm_product', '=', False)
        ])

        self.assertNotIn(fsm_cat, non_fsm_categories)
        self.assertIn(non_fsm_cat1, non_fsm_categories)
        self.assertIn(non_fsm_cat2, non_fsm_categories)

    def test_parent_child_category_fsm_flag(self):
        """Test that parent and child categories have independent FSM flags"""
        parent_fsm = self.ProductCategory.create({
            'name': 'Parent FSM',
            'is_fsm_product': True,
        })
        child_non_fsm = self.ProductCategory.create({
            'name': 'Child Non-FSM',
            'parent_id': parent_fsm.id,
            'is_fsm_product': False,
        })

        self.assertTrue(parent_fsm.is_fsm_product)
        self.assertFalse(child_non_fsm.is_fsm_product)

    def test_parent_child_category_both_fsm(self):
        """Test parent and child categories both with FSM flag enabled"""
        parent_fsm = self.ProductCategory.create({
            'name': 'Parent FSM',
            'is_fsm_product': True,
        })
        child_fsm = self.ProductCategory.create({
            'name': 'Child FSM',
            'parent_id': parent_fsm.id,
            'is_fsm_product': True,
        })

        self.assertTrue(parent_fsm.is_fsm_product)
        self.assertTrue(child_fsm.is_fsm_product)

    def test_product_in_fsm_category(self):
        """Test that products in FSM categories are correctly associated"""
        fsm_category = self.ProductCategory.create({
            'name': 'FSM Services',
            'is_fsm_product': True,
        })

        product = self.env['product.product'].create({
            'name': 'FSM Service Product',
            'type': 'service',
            'categ_id': fsm_category.id,
        })

        self.assertEqual(product.categ_id, fsm_category)
        self.assertTrue(product.categ_id.is_fsm_product)

    def test_product_category_switch_flag(self):
        """Test switching a product category FSM flag after creating products in it"""
        category = self.ProductCategory.create({
            'name': 'Service Products',
            'is_fsm_product': False,
        })

        product = self.env['product.product'].create({
            'name': 'Service Product',
            'type': 'service',
            'categ_id': category.id,
        })

        # Initially not FSM
        self.assertFalse(product.categ_id.is_fsm_product)

        # Switch the flag
        category.is_fsm_product = True

        # Now the product's category is FSM
        self.assertTrue(product.categ_id.is_fsm_product)

    def test_write_multiple_categories_fsm_flag(self):
        """Test bulk updating FSM flag on multiple categories"""
        categories = self.ProductCategory.create([
            {'name': 'Cat 1', 'is_fsm_product': False},
            {'name': 'Cat 2', 'is_fsm_product': False},
            {'name': 'Cat 3', 'is_fsm_product': False},
        ])

        categories.write({'is_fsm_product': True})

        for category in categories:
            self.assertTrue(category.is_fsm_product)
