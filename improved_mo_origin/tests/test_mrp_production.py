from odoo.addons.sale_mrp.tests.test_sale_mrp_flow import TestSaleMrpFlowCommon
from odoo.tests import Form, tagged


@tagged("-at_install", "post_install")
class TestMrpProduction(TestSaleMrpFlowCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def _setup_products(self):
        route_manufacture = self.company_data[
            "default_warehouse"
        ].manufacture_pull_id.route_id
        route_mto = self.company_data["default_warehouse"].mto_pull_id.route_id
        product_a = self._cls_create_product(
            "Product A",
            self.uom_unit,
            routes=[route_manufacture, route_mto],
        )
        product_c = self._cls_create_product(
            "Product C",
            self.uom_kg,
        )
        product_b = self._cls_create_product(
            "Product B",
            self.uom_dozen,
            routes=[route_manufacture, route_mto],
        )
        product_d = self._cls_create_product(
            "Product D",
            self.uom_unit,
            routes=[route_manufacture, route_mto],
        )
        # Bill of materials for Product A.
        with Form(self.env["mrp.bom"]) as form:
            form.product_tmpl_id = product_a.product_tmpl_id
            form.product_id = product_a
            form.product_qty = 2
            form.product_uom_id = self.uom_dozen
            form.save()
            with form.bom_line_ids.new() as line:
                line.product_id = product_b
                line.product_qty = 3
                line.product_uom_id = self.uom_unit
            with form.bom_line_ids.new() as line:
                line.product_id = product_c
                line.product_qty = 300.0
                line.product_uom_id = self.uom_gm
            with form.bom_line_ids.new() as line:
                line.product_id = product_d
                line.product_qty = 4
                line.product_uom_id = self.uom_unit
        # Bill of materials for Product B.
        with Form(self.env["mrp.bom"]) as form:
            form.product_tmpl_id = product_b.product_tmpl_id
            form.product_id = product_b
            form.product_qty = 1
            form.product_uom_id = self.uom_dozen
            form.save()
            with form.bom_line_ids.new() as line:
                line.product_id = product_d
                line.product_qty = 2
                line.product_uom_id = self.uom_unit
        return product_a

    def _create_order(self, partner_name: str, product):
        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.env["res.partner"].create({"name": partner_name})
        with order_form.order_line.new() as line:
            line.product_id = product
            line.product_uom = self.uom_dozen
            line.product_uom_qty = 10
        return order_form.save()

    def _setup_test_mo_single_client(self):
        product_a = self._setup_products()

        order = self._create_order("Test Partner", product_a)
        order.action_confirm()
        # A sales order creating an MO should have its partner listed in the MO's customer_ids field

        self.assertNotEqual(order.mrp_production_count, 0)
        base_mos = order.mrp_production_ids | order.mrp_production_ids
        child_mos = self.env["mrp.production"]
        for mo in base_mos:
            child_mos |= mo._get_children()
        return order, base_mos | child_mos

    def test_mo_single_client_correctly_listed(self):
        order, all_mos = self._setup_test_mo_single_client()
        for mo in all_mos:
            self.assertIn(order.partner_id, mo.customer_ids)

    def test_mo_single_client_so_correctly_set(self):
        order, all_mos = self._setup_test_mo_single_client()
        for mo in all_mos:
            self.assertEqual(order.name, mo.source_sale_orders)

    def _setup_test_mo_multiple_so(self):
        product_a = self._setup_products()
        order1 = self._create_order("Test Partner 1", product_a)
        order2 = self._create_order("Test Partner 2", product_a)
        order1.action_confirm()
        order2.action_confirm()

        # Run scheduler to create manufacturing orders with proper BOMs
        self.env["procurement.group"].run_scheduler()

        # Get top-level MOs for Product A only (not child MOs for components)
        top_level_mos_order1 = order1.mrp_production_ids.filtered(
            lambda mo: mo.product_id == product_a
        )
        top_level_mos_order2 = order2.mrp_production_ids.filtered(
            lambda mo: mo.product_id == product_a
        )

        # Merge only the top-level MOs for the same product
        (top_level_mos_order1 | top_level_mos_order2).action_merge()
        self.env.invalidate_all(flush=True)

        # After merge, find the merged MO (original MOs are deleted, new one created)
        merged_mos = self.env['mrp.production'].search([
            ('product_id', '=', product_a.id),
            ('state', 'in', ['draft', 'confirmed', 'progress', 'to_close']),
        ])
        
        self.assertTrue(merged_mos, "Should find the merged MO")
        self.assertEqual(len(merged_mos), 1, "Should have exactly one merged MO")
        merged_mo = merged_mos[0]

        # Collect all MOs (merged top-level + all children)
        all_mos = merged_mo
        for mo in merged_mo:
            all_mos |= mo._get_children()

        return order1, order2, all_mos

    def test_mo_multiple_so_clients_correctly_listed(self):
        order1, order2, all_mos = self._setup_test_mo_multiple_so()
        # MOs are merged so we should get both partners on each MO
        for mo in all_mos:
            self.assertIn(order1.partner_id, mo.customer_ids)
            self.assertIn(order2.partner_id, mo.customer_ids)

    def test_mo_multiple_so_sales_correctly_set(self):
        order1, order2, all_mos = self._setup_test_mo_multiple_so()
        # MOs are merged so both sale_ids should be set on all MOs
        for mo in all_mos:
            self.assertIn(order1.name, mo.source_sale_orders)
            self.assertIn(order2.name, mo.source_sale_orders)
