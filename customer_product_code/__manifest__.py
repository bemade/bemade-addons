{
    "name": "Customer Product Codes",
    "version": "19.0.2.0.0",
    "summary": "Customer-specific product codes and names on quotations, "
    "invoices and deliveries",
    "description": """
Customer Product Codes
======================

Many customers order using their own part numbers and descriptions rather than
ours. This module records, for each customer, the code and name they use for a
product, and shows them wherever that customer's documents are prepared.

Features
--------

**Customer codes**

* A *customer product code* links a customer, a product and (optionally) a
  company to the customer's own code and name for that product. Codes can be
  archived.
* A customer has at most one code per product and company. The same code may be
  used on several products, for when the customer accepts an equivalent part.
* Codes are managed from a *Customer Codes* tab on the product form, and from
  *Sales > Configuration > Customer Product Codes*.
* Duplicating a product does not duplicate its customer codes.

**Contacts use their company's codes**

* Wherever a customer is looked up, a code recorded on the customer's company
  (commercial partner) also applies to the company's contacts and addresses.

**Sales orders**

* When a product is added to a sales order line, the line description uses the
  customer's code and name: ``[CODE] Name``, followed by the product's sales
  description on the next line when there is one. If the customer left the code
  or the name blank, the product's internal reference or name is used instead.

**Product names and search**

* When a customer is known (invoice lines, delivery moves), products display as
  ``[CODE] Name`` using that customer's code and name.
* Products can be found by a customer's code or name. With a customer known, only
  that customer's (and its company's) codes are searched; otherwise all codes are.
* The product's *Customer Ref* (``partner_ref``) shows the customer's code and
  name.
* Product and product variant search views can filter by customer product code.

**Product list**

* Product templates are listed by internal reference, then name, with the
  internal reference column shown first.

**Security**

* All internal users can read customer codes; salespeople can create, edit and
  delete them. The *Customer Product Codes* menu is shown to members of the
  *Product_Customer / Manager* group.

Compatibility
-------------

This is a drop-in LGPL-3 replacement for the commercial ``customer_product_code``
module. It keeps the technical name, the ``product.customer.code`` model and
table, all field names, the security groups, the XML IDs other modules rely on,
and the ``has_customer_code()`` and ``_get_partner_code_name()`` methods, so an
installed database upgrades in place with no data migration. Supplier codes on
vendor bills are left to standard Odoo, which already provides them.
""",
    "category": "Sales/Sales",
    "author": "Bemade Inc.",
    "maintainer": "Marc Durepos <marc@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["sale_management", "account", "stock"],
    "data": [
        "security/customer_product_code_security.xml",
        "security/ir.model.access.csv",
        "views/product_customer_code_views.xml",
        "views/product_views.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
