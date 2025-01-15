from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("post_install", "-at_install")
class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_default_carrier_set_on_create(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "carrier_account_ids": [
                    Command.create(
                        {
                            "delivery_carrier_id": self.env.ref(
                                "delivery.free_delivery_carrier"
                            ).id,
                            "account_number": "1234567890",
                        }
                    )
                ],
            }
        )

        self.assertEqual(
            partner.carrier_account_ids[0], partner.default_carrier_account_id
        )
