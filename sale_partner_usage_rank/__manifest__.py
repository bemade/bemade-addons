{
    "name": "Sale Partner Usage Rank",
    "version": "19.0.1.0.0",
    "summary": "Rank and default sales order contacts and addresses by how often they are used",
    "category": "Sales/Sales",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["sale"],
    "description": """
Sale Partner Usage Rank
=======================

Puts the contacts and addresses a customer actually uses at the top of the
sales order dropdowns, and defaults the addresses to the ones used most
often, instead of the first one Odoo finds.

Usage ranks
-----------

Three stored counters on contacts, in the spirit of ``customer_rank``:

- ``sale_contact_rank``: number of sales orders and quotations with this
  partner as **Customer** (``partner_id``).
- ``sale_shipping_rank``: number with this partner as **Delivery Address**
  (``partner_shipping_id``).
- ``sale_invoice_rank``: number with this partner as **Invoice Address**
  (``partner_invoice_id``).

Every order counts, whatever its state. The counters stay exact: they go up
when an order is created, move from the old partner to the new one when the
field changes, and go down when an order is deleted. Installing the module
fills them in from existing orders.

Dropdown order
--------------

On the sales order form:

- **Customer** suggestions come most-used first (``sale_contact_rank``).
- **Delivery Address** and **Invoice Address** suggestions start with the
  addresses of the order's customer contact's company and any address that
  contact has used, before other companies' addresses; within each group,
  by uses with that contact, then by uses overall (``sale_shipping_rank`` /
  ``sale_invoice_rank``).

A module can make a slot prefer some partners
(``res.partner._sale_usage_eligible_sql``): they come first within each
group, and only they become the slot's default.

Ties, and partners never used, keep Odoo's usual order. Ranking only
reorders what the search finds: what matches a search, and match quality
tiers added by other modules (e.g. ``base_name_search_improved``), are
unchanged. Other partner fields in Odoo are not affected.

Address defaults
----------------

When the customer contact is set or changed, Delivery Address and Invoice
Address default to:

#. the address used most often with that contact on earlier orders;
#. otherwise, the most used address within the contact's company;
#. otherwise, Odoo's standard choice.

A user can still pick any other address.
""",
    "post_init_hook": "_backfill_sale_usage_ranks",
    "installable": True,
}
