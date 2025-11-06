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
