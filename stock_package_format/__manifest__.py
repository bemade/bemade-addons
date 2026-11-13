# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
{
    "name": "Stock Package Format",
    "version": "19.0.1.0.0",
    "summary": "Stock bulk products in real packages of fixed formats (bag, drum, "
    "bulk bag...), one lot per package, never split by accident.",
    "description": """Stock Package Format
====================

Some products are counted in a base unit (a cubic foot, a litre...) but always
live inside physical packages of a few fixed formats: 1 ft³ bags, 5 ft³ drums,
42 ft³ bulk bags. This module keeps those packages real in the stock, each with
its supplier lot, so you know at any time both the total quantity of a product
and how many packages of each format you hold.

Configuration
-------------

* A product's **formats** are its packaging units (*Packagings* on the product,
  e.g. a "Drum" unit worth 5 ft³). Each format unit points to a **package
  type** (field *Package Type* on the unit).
* Turn the rule on with **Track in package formats** on a product category,
  and override it per product (*Category* / *Always* / *Never*). A product can
  only use the rule when it is tracked by lots and has at least one format
  unit with a package type. Products without the rule behave exactly as in
  standard Odoo.
* Users of the new group **Can open packages** (granted to inventory
  administrators) may open and repack packages.

Receiving
---------

Validating a receipt (or clicking **Pack by format**) opens one dialog that
creates all the packages at once: one package per format unit, of the
format's package type, with its lot. One lot for the whole line by default;
add rows to split a line between lots (30 bags lot A + 12 bags lot B). A
package always holds exactly one lot. A line received in the base unit asks
for the format (the product's smallest format by default). A quantity that
is not a whole number of packages is refused. The package labels print as
one batch.

Reservation: whole packages only
--------------------------------

* A move in a format unit (2 drums) reserves only unopened, free packages of
  that format, whole.
* A move in the base unit (3 ft³ for a tank, a manufacturing order
  component) reserves only loose stock and the content of **opened**
  packages. When that is short, the move and the sale line propose the
  smallest unopened package that covers the need; opening it stays an
  explicit action.
* The rule sits at the quant reservation level, so every path that reserves
  stock obeys it. Validating a transfer that takes part of an unopened
  package is refused.

Open and repack
---------------

* **Open** flags a package as opened (who, when, why, logged in its chatter);
  any quantity can then be taken from it and the rest stays in the package
  with its lot.
* **Repack** moves a quantity of one lot from an opened package or from loose
  stock into new packages of another format (a 42 ft³ bulk bag into 42 bags).

Sales and purchase
------------------

On a quotation line in a format, the availability popover shows how many
packages of that format are free and how many must be bought. On
confirmation, the shortfall is bought to order: a request for quotation
line in that format unit, linked to the sale line. Reordering rules in the
base unit never merge into that line.

Reporting and go-live
---------------------

* The product form sums up the packages in stock per format and lot, and
  *Inventory > Reporting > Stock by Package Format* lists them.
* **Pack existing stock** (on the product) packs loose stock into N packages
  of a format with a lot, through an inventory adjustment, for the day a
  product starts using the rule.
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "category": "Inventory/Inventory",
    "depends": ["sale_purchase_stock"],
    "data": [
        "security/stock_package_format_security.xml",
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/stock_package_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_quant_views.xml",
        "views/sale_order_views.xml",
        "wizard/pack_wizard_views.xml",
        "wizard/open_wizard_views.xml",
        "wizard/repack_wizard_views.xml",
        "wizard/golive_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stock_package_format/static/src/sale_qty_popover/*",
        ],
    },
    "installable": True,
    "auto_install": False,
}
