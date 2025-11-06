from .test_carrier_account_common import TestCarrierAccountCommon
from odoo.exceptions import UserError
from odoo.tests import Form

import logging

_logger = logging.getLogger(__name__)


class TestCarrierAccountMixin(TestCarrierAccountCommon):
    def test_compute_account_collect_order(self):
        order = self._create_sale_order(
            "collect",
            self.delivery_carrier_1,
            False,
        )
        self.assertEqual(order.carrier_account_id, self.client_account_1)

    def test_compute_account_prepaid_order(self):
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.client_partner.id,
                "carrier_id": self.delivery_carrier_2.id,
                "picking_type_id": self.env.ref("stock.warehouse0").out_type_id.id,
                "delivery_billing_mode": "prepaid",
            }
        )
        self.assertEqual(picking.carrier_account_id, self.sender_account_2)

    def test_compute_account_ppc_order(self):
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.client_partner.id,
                "carrier_id": self.delivery_carrier_2.id,
                "picking_type_id": self.env.ref("stock.warehouse0").out_type_id.id,
                "delivery_billing_mode": "ppc",
            }
        )
        self.assertEqual(picking.carrier_account_id, self.sender_account_2)

    def test_compute_account_third_party_order(self):
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.client_partner.id,
                "carrier_id": self.delivery_carrier_2.id,
                "picking_type_id": self.env.ref("stock.warehouse0").out_type_id.id,
                "delivery_billing_mode": "prepaid",
            }
        )
        with Form(picking) as form:  # Use a form here to trigger recomputation
            form.delivery_billing_mode = "third party"
        picking = form.record
        self.assertFalse(picking.carrier_account_id)

    def test_changing_account_on_confirmed_sale_changes_picking(self):
        new_account = self.env["delivery.carrier.account"].create(
            {
                "partner_id": self.client_partner.id,
                "delivery_carrier_id": self.delivery_carrier_1.id,
                "account_number": "1234567891",
            }
        )
        order = self._create_sale_order("collect", self.delivery_carrier_1, False)
        order.action_confirm()
        order.carrier_account_id = new_account
        self.assertEqual(order.picking_ids.carrier_account_id, new_account)

    def test_incorrect_collect_account(self):
        with self.assertRaises(UserError):
            self._create_sale_order(
                "collect",
                self.delivery_carrier_1,
                self.sender_account_1,
            )
        with self.assertRaises(UserError):
            self._create_sale_order(
                "collect",
                self.delivery_carrier_1,
                self.third_party_account_1,
            )

    def test_incorrect_prepaid_account(self):
        with self.assertRaises(UserError):
            self._create_sale_order(
                "prepaid",
                self.delivery_carrier_1,
                self.client_account_1,
            )
        with self.assertRaises(UserError):
            self._create_sale_order(
                "prepaid",
                self.delivery_carrier_1,
                self.third_party_account_1,
            )

    def test_incorrect_ppc_account(self):
        with self.assertRaises(UserError):
            self._create_sale_order(
                "ppc",
                self.delivery_carrier_1,
                self.client_account_1,
            )
        with self.assertRaises(UserError):
            self._create_sale_order(
                "ppc",
                self.delivery_carrier_1,
                self.third_party_account_1,
            )

    def test_incorrect_third_party_account(self):
        with self.assertRaises(UserError):
            self._create_sale_order(
                "third party", self.delivery_carrier_1, self.client_account_1
            )
        with self.assertRaises(UserError):
            self._create_sale_order(
                "third party", self.delivery_carrier_1, self.sender_account_1
            )

    def test_carrier_preserved_on_billing_mode_change(self):
        """Test that changing billing mode preserves carrier when valid account exists."""
        # Create a collect account for the same carrier
        collect_account = self.env["delivery.carrier.account"].create(
            {
                "delivery_carrier_id": self.delivery_carrier_1.id,
                "account_number": "COLLECT123",
                "partner_id": self.client_partner.id,
            }
        )
        self.client_partner.write(
            {"property_delivery_carrier_id": self.delivery_carrier_2.id}
        )

        # Create an order with prepaid billing and carrier 1
        order = self._create_sale_order(
            billing_mode=False,
            carrier=self.delivery_carrier_1,
            account=False,
        )
        self.assertEqual(order.carrier_id, self.delivery_carrier_1)
        self.assertFalse(order.delivery_billing_mode)

        # Change billing mode to collect - carrier should stay the same
        # since there's a valid collect account for it
        with Form(order) as form:
            form.delivery_billing_mode = "collect"
            self.assertEqual(
                form.carrier_id,
                self.delivery_carrier_1,
                "Carrier should not change when switching billing mode if a valid account exists",
            )
