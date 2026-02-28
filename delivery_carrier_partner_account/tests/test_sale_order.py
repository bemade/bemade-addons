from .test_carrier_account_common import TestCarrierAccountCommon
from odoo.tests import Form
from odoo import Command, api


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

    def test_sale_order_shipping_to_third_party_collect(self):
        # We create an order where we are shipping to a third party and the billing mode is collect
        # This should work, but was previously failing with an error that the carrier account did not belong to the recipient
        order = self.env["sale.order"].create(
            {
                "partner_id": self.client_partner.id,
                "partner_shipping_id": self.random_partner.id,
                "order_line": [
                    Command.create(
                        {"product_id": self.storable_product.id}
                    )
                ],
            }
        )
        # Confirming the order is important because the sender and recipient need to be in sync
        # on the sale order and delivery order. This was the point of failure previously.
        order.action_confirm()

        wiz = self._get_shipping_wizard(order)
        with Form(wiz) as form:
            form.carrier_id = self.delivery_carrier_1
            form.delivery_billing_mode = "collect"
        self.assertIn(self.third_party_account_1, wiz.valid_carrier_account_ids)
        wiz.button_confirm()

        self.assertEqual(
            order.carrier_account_id.partner_id,
            self.random_partner,
            "The carrier account should belong to the recipient (sale order shipping address)",
        )

    def test_stock_picking_inherits_carrier_info(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.client_partner.id,
                "partner_shipping_id": self.client_partner.id,
                "order_line": [
                    Command.create(
                        {"product_id": self.storable_product.id}
                    )
                ],
                "carrier_id": self.delivery_carrier_1.id,
                "delivery_billing_mode": "collect",
                "carrier_account_id": self.client_account_1.id,
            }
        )
        order.action_confirm()
        self.env.flush_all()

        picking = order.picking_ids
        self.assertEqual(picking.carrier_id, order.carrier_id)
        self.assertEqual(picking.delivery_billing_mode, order.delivery_billing_mode)
        self.assertEqual(picking.carrier_account_id, order.carrier_account_id)

    def _get_shipping_wizard(self, order):
        wizard_action = order.action_open_delivery_wizard()
        return (
            self.env[wizard_action["res_model"]]
            .with_context(wizard_action["context"])
            .create({})
        )
