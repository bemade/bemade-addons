from odoo.addons.bemade_fsm.tests.test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests import tagged, Form


@tagged("-at_install", "post_install")
class TestEquipment(BemadeFSMBaseTest):
    def test_equipment_search_domain_on_sale_order(self):
        """Equipment from other clients was showing up in sale order line
        equipment choices. Make sure this doesn't happen."""
        partner = self._generate_partner()
        partner_2 = self._generate_partner()
        equipment_1 = self._generate_equipment(partner=partner)
        equipment_2 = self._generate_equipment(partner=partner_2)
        sale_order = self._generate_sale_order(partner=partner)
        product = self._generate_product()
        self.assertEqual(sale_order.valid_equipment_ids, equipment_1)

        name_search_results = self.env["fsm.equipment"].name_search(
            args=[
                "&",
                ["id", "in", sale_order.valid_equipment_ids.ids],
                "!",
                ["id", "in", []],
            ],
            limit=8,
            name="test",
            operator="ilike",
        )
        self.assertNotIn(
            (equipment_2.id, equipment_2.display_name), name_search_results
        )
        self.assertIn((equipment_1.id, equipment_1.display_name), name_search_results)
