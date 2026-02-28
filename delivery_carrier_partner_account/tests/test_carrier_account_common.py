from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("-at_install", "post_install")
class TestCarrierAccountCommon(TransactionCase):
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
        cls.delivery_carrier_1 = cls.env["delivery.carrier"].create(
            {
                "name": "Test Carrier 1",
                "delivery_type": "fixed",
                "product_id": delivery_product_1.id,
                "fixed_price": 0.0,
            }
        )
        cls.delivery_carrier_2 = cls.env["delivery.carrier"].create(
            {
                "name": "Test Carrier 2",
                "delivery_type": "fixed",
                "product_id": delivery_product_2.id,
                "fixed_price": 10.0,
            }
        )
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
        cls.test_product = cls.env["product.product"].create(
            {
                "name": "Test Sale Product",
                "list_price": 100.0,
            }
        )
        cls.storable_product = cls.env["product.product"].create(
            {
                "name": "Test Storable Product",
                "is_storable": True,
                "list_price": 50.0,
            }
        )

    def _create_sale_order(self, billing_mode, carrier, account):
        vals = {
            "partner_id": self.client_partner.id,
            "carrier_id": carrier.id,
            "delivery_billing_mode": billing_mode,
            "order_line": [
                Command.create(
                    {
                        "product_id": self.test_product.id,
                    }
                )
            ],
        }
        if account:
            vals["carrier_account_id"] = account.id
        return self.env["sale.order"].create(vals)
