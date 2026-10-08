from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class CustomerProductCodeCase(TransactionCase):
    """Shared fixtures.

    * ``customer``: a company with a contact (``contact``) and a delivery
      address (``delivery_address``);
    * ``other_customer``: an unrelated company;
    * ``product``: internal reference ``INT-1``, name ``Widget``, with a sales
      description;
    * ``code``: ``customer``'s code on ``product``, ``CUST-1`` / ``Customer
      Widget``;
    * ``other_code``: ``other_customer``'s code on ``product``, ``OTHER-1`` /
      ``Other Widget``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        cls.customer = Partner.create({"name": "Acme Corp", "is_company": True})
        cls.contact = Partner.create(
            {"name": "Jane Buyer", "parent_id": cls.customer.id}
        )
        cls.delivery_address = Partner.create(
            {
                "name": "Acme Warehouse",
                "type": "delivery",
                "parent_id": cls.customer.id,
            }
        )
        cls.other_customer = Partner.create(
            {"name": "Globex", "is_company": True}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Widget",
                "default_code": "INT-1",
                "description_sale": "Sales blurb",
                "type": "consu",
                "list_price": 10.0,
            }
        )
        cls.template = cls.product.product_tmpl_id
        Code = cls.env["product.customer.code"]
        cls.code = Code.create(
            {
                "partner_id": cls.customer.id,
                "product_id": cls.template.id,
                "product_code": "CUST-1",
                "product_name": "Customer Widget",
            }
        )
        cls.other_code = Code.create(
            {
                "partner_id": cls.other_customer.id,
                "product_id": cls.template.id,
                "product_code": "OTHER-1",
                "product_name": "Other Widget",
            }
        )

    def _create_product(self, name, default_code=None, **vals):
        return self.env["product.product"].create(
            {"name": name, "default_code": default_code, "type": "consu", **vals}
        )

    def _add_code(self, partner, product, code, name=None):
        return self.env["product.customer.code"].create(
            {
                "partner_id": partner.id,
                "product_id": product.product_tmpl_id.id,
                "product_code": code,
                "product_name": name,
            }
        )
