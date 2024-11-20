from odoo.tests import TransactionCase, tagged, mute_logger
from odoo import Command
from odoo.exceptions import UserError


@tagged("-at_install", "post_install")
class TestCarrierAccountMixin(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client_partner = cls.env["res.partner"].create(
            {
                "name": "Test partner",
            }
        )
        cls.random_partner = cls.env["res.partner"].create(
            {
                "name": "Third Party",
            }
        )
        cls.delivery_carrier_1 = cls.env.ref("delivery.free_delivery_carrier")
        cls.delivery_carrier_2 = cls.env.ref("delivery.delivery_local_delivery")
        cls.client_account_1 = cls.env["delivery.carrier.account"].create(
            {
                "partner_id": cls.client_partner.id,
                "delivery_carrier_id": cls.delivery_carrier_1.id,
                "account_number": "1234567890",
            }
        )
        cls.client_account_2 = cls.env["delivery.carrier.account"].create(
            {
                "partner_id": cls.client_partner.id,
                "delivery_carrier_id": cls.delivery_carrier_2.id,
                "account_number": "0987654321",
            }
        )
        cls.sender_account_1 = cls.env["delivery.carrier.account"].create(
            {
                "partner_id": cls.env.company.partner_id.id,
                "delivery_carrier_id": cls.delivery_carrier_1.id,
                "account_number": "hijklmn",
            }
        )
        cls.sender_account_2 = cls.env["delivery.carrier.account"].create(
            {
                "partner_id": cls.env.company.partner_id.id,
                "delivery_carrier_id": cls.delivery_carrier_2.id,
                "account_number": "abcdefg",
            }
        )
        cls.third_party_account_1 = cls.env["delivery.carrier.account"].create(
            {
                "partner_id": cls.random_partner.id,
                "delivery_carrier_id": cls.delivery_carrier_1.id,
                "account_number": "8910111213",
            }
        )
        cls.third_party_account_2 = cls.env["delivery.carrier.account"].create(
            {
                "partner_id": cls.random_partner.id,
                "delivery_carrier_id": cls.delivery_carrier_2.id,
                "account_number": "zzzzzzzzz",
            }
        )

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

    def test_compute_account_third_party_order(self):
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.client_partner.id,
                "carrier_id": self.delivery_carrier_2.id,
                "picking_type_id": self.env.ref("stock.warehouse0").out_type_id.id,
                "delivery_billing_mode": "prepaid",
            }
        )
        # No need to assert we have an account selected here. Tested elsewhere.
        picking.delivery_billing_mode = "third party"
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

    def test_incorrect_third_party_account(self):
        with self.assertRaises(UserError):
            self._create_sale_order(
                "third party", self.delivery_carrier_1, self.client_account_1
            )
        with self.assertRaises(UserError):
            self._create_sale_order(
                "third party", self.delivery_carrier_1, self.sender_account_1
            )

    def _create_sale_order(self, billing_mode, carrier, account):
        vals = {
            "partner_id": self.client_partner.id,
            "carrier_id": carrier.id,
            "delivery_billing_mode": billing_mode,
            "order_line": [
                Command.create(
                    {
                        "product_id": self.env.ref("product.product_product_4").id,
                    }
                )
            ],
        }
        if account:
            vals["carrier_account_id"] = account.id
        return self.env["sale.order"].create(vals)
