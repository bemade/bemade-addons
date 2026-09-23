from odoo.tests import TransactionCase


class CustomerProductCodeCase(TransactionCase):
    """Shared fixtures (implementation pending use-case agreement).

    Planned fixtures:

    * ``customer``: a company partner with a contact (``contact``) and a
      delivery address (``delivery_address``);
    * ``other_customer``: an unrelated company partner;
    * ``product``: a consumable with internal reference ``INT-1``, name
      ``Widget`` and a sales description;
    * ``code``: a customer code on ``product`` for ``customer``,
      ``CUST-1`` / ``Customer Widget``;
    * ``other_code``: a code on ``product`` for ``other_customer``,
      ``OTHER-1`` / ``Other Widget``.
    """
