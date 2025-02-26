from .test_carrier_account_common import TestCarrierAccountCommon
from odoo.tests import Form


class TestSalesOrder(TestCarrierAccountCommon):
    def test_sales_order_creation_with_default_account(self):
        self.client_partner.property_delivery_carrier_id = self.delivery_carrier_1
        self.client_partner.default_carrier_account_id = self.client_account_1
        self.env["sale.order"].create({"partner_id": self.client_partner.id})

    def test_collect_sale_order_line_gets_proper_name(self):
        order = self.env["sale.order"].create({"partner_id": self.client_partner.id})
        wiz = self._get_shipping_wizard(order)
        wiz.carrier_id = self.delivery_carrier_1
        wiz.delivery_billing_mode = "collect"
        wiz.button_confirm()
        self.assertEqual(
            order.order_line[0].name,
            f"{self.delivery_carrier_1.name} [COLLECT] #{self.client_account_1.account_number}",
        )

    def test_prepaid_sale_order_line_gets_proper_name(self):
        order = self.env["sale.order"].create({"partner_id": self.client_partner.id})
        wiz = self._get_shipping_wizard(order)
        with Form(wiz) as form:
            form.carrier_id = self.delivery_carrier_2
            form.delivery_billing_mode = "prepaid"
        wiz.button_confirm()
        self.assertEqual(
            order.order_line[0].name,
            f"{self.delivery_carrier_2.name} [PREPAID]",
        )

    def test_third_party_sale_order_line_gets_proper_name(self):
        order = self.env["sale.order"].create({"partner_id": self.client_partner.id})
        wiz = self._get_shipping_wizard(order)
        wiz.carrier_id = self.delivery_carrier_1
        wiz.delivery_billing_mode = "third party"
        wiz.carrier_account_id = self.third_party_account_1
        wiz.button_confirm()
        self.assertEqual(order.carrier_account_id, self.third_party_account_1)
        self.assertEqual(
            order.order_line[0].name,
            f"{self.delivery_carrier_1.name} [THIRD PARTY] #{self.third_party_account_1.account_number}",
        )

    def _get_shipping_wizard(self, order):
        wizard_action = order.action_open_delivery_wizard()
        return (
            self.env[wizard_action["res_model"]]
            .with_context(wizard_action["context"])
            .create({})
        )
