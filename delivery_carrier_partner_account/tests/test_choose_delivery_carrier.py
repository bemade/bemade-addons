from .test_carrier_account_common import TestCarrierAccountCommon


class TestChooseDeliveryCarrier(TestCarrierAccountCommon):
    def test_sale_order_add_transport(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.client_partner.id,
            }
        )
        wizard_action = order.action_open_delivery_wizard()

        wizard = (
            self.env[wizard_action["res_model"]]
            .with_context(wizard_action["context"])
            .create({})
        )
        wizard.carrier_id = self.delivery_carrier_1
        wizard.delivery_billing_mode = "collect"
        wizard.button_confirm()
        self.assertEqual(order.carrier_id, self.delivery_carrier_1)
        self.assertEqual(order.carrier_account_id, self.client_account_1)
        self.assertEqual(order.delivery_billing_mode, "collect")
