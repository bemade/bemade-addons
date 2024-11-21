from .test_carrier_account_common import TestCarrierAccountCommon


class TestSalesOrder(TestCarrierAccountCommon):
    def test_sales_order_creation_with_default_account(self):
        self.client_partner.property_delivery_carrier_id = self.delivery_carrier_1
        self.client_partner.default_carrier_account_id = self.client_account_1
        self.env["sale.order"].create({"partner_id": self.client_partner.id})
