from odoo.tests import TransactionCase, tagged, Form
from odoo import Command


@tagged("post_install", "-at_install")
class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        delivery_product_1 = cls.env["product.product"].create(
            {
                "name": "Test Delivery Product 1",
                "type": "service",
            }
        )
        delivery_product_2 = cls.env["product.product"].create(
            {
                "name": "Test Delivery Product 2",
                "type": "service",
            }
        )
        cls.carrier_1 = cls.env["delivery.carrier"].create(
            {
                "name": "Test Carrier 1",
                "delivery_type": "fixed",
                "product_id": delivery_product_1.id,
                "fixed_price": 0.0,
            }
        )
        cls.carrier_2 = cls.env["delivery.carrier"].create(
            {
                "name": "Test Carrier 2",
                "delivery_type": "fixed",
                "product_id": delivery_product_2.id,
                "fixed_price": 10.0,
            }
        )

    def test_default_carrier_set_on_create(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        account = self.env["delivery.carrier.account"].create(
            {
                "partner_id": partner.id,
                "delivery_carrier_id": self.carrier_1.id,
                "account_number": "1234567890",
            }
        )

        self.assertEqual(
            partner.carrier_account_ids[0], partner.default_carrier_account_id
        )

    def test_default_carrier_set_on_update(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        partner.write(
            {
                "carrier_account_ids": [
                    Command.create(
                        {
                            "delivery_carrier_id": self.carrier_1.id,
                            "account_number": "1234567890",
                        }
                    )
                ]
            }
        )
        self.assertEqual(
            partner.carrier_account_ids[0], partner.default_carrier_account_id
        )

    def test_no_change_to_default_account_id_on_update_if_already_set(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "carrier_account_ids": [
                    Command.create(
                        {
                            "delivery_carrier_id": self.carrier_1.id,
                            "account_number": "1234567890",
                        }
                    )
                ],
            }
        )
        new_account = self.env["delivery.carrier.account"].create(
            {
                "partner_id": partner.id,
                "delivery_carrier_id": self.carrier_2.id,
                "account_number": "1234567890",
            }
        )
        self.assertNotEqual(partner.default_carrier_account_id, new_account)

    def test_carrier_set_if_account_created_from_other_side(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        new_account = self.env["delivery.carrier.account"].create(
            {
                "partner_id": partner.id,
                "delivery_carrier_id": self.carrier_1.id,
                "account_number": "1234567890",
            }
        )

        self.assertEqual(partner.default_carrier_account_id, new_account)

    def test_no_archived_default_carrier_account(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        account = self.env["delivery.carrier.account"].create(
            {
                "partner_id": partner.id,
                "delivery_carrier_id": self.carrier_1.id,
                "account_number": "1234567890",
            }
        )

        with Form(account) as account_form:
            account_form.active = False

        self.assertFalse(partner.default_carrier_account_id)

    def test_multiple_carrier_accounts_reset_default_on_archive(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        account1 = self.env["delivery.carrier.account"].create(
            {
                "partner_id": partner.id,
                "delivery_carrier_id": self.carrier_1.id,
                "account_number": "1234567890",
            }
        )
        account2 = self.env["delivery.carrier.account"].create(
            {
                "partner_id": partner.id,
                "delivery_carrier_id": self.carrier_1.id,
                "account_number": "1234567891",
            }
        )
        self.assertEqual(partner.default_carrier_account_id, account1)
        with Form(account1) as account_form:
            account_form.active = False
        self.assertEqual(partner.default_carrier_account_id, account2)
