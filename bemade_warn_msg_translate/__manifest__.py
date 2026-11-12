# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Translatable Warning Messages",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Make customer, vendor, delivery and product warnings translatable.",
    "description": """
Translatable Warning Messages
=============================

Odoo's warning messages are plain text: a company working in two languages
ends up typing both versions in the same field, and every user reads both on
every quotation, order and delivery. This module makes the five warning
fields translatable, so each user only sees the version in their language.

Features
--------

* ``translate=True`` on the stock warning fields:

  * customer / vendor: *Message for Sales Order*, *Message for Purchase
    Order*, *Message for Stock Picking*;
  * product: *Sales Order Line Warning*, *Message for Purchase Order Line*.

* Every place that shows these warnings (sales and purchase order banners,
  line warnings, delivery-order banner, Point of Sale) reads them in the
  user's language with no further change. The fields get the usual
  translation globe on the customer and product forms.

* On installation, existing bilingual warnings written as « French
  paragraph(s), blank line, English paragraph(s) » are split automatically:
  the French part becomes the value of every active French language, the
  English part the ``en_US`` value. A text is split only on one clear
  French-to-English switch between paragraphs of comparable length;
  anything else (single language, English first, mixed or unclear) is left
  as it is and still shows in every language. The counts per field are
  logged.

* On uninstallation, translated values are folded back into one bilingual
  text (French first) before the columns return to plain text, so nothing
  is lost.
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "depends": ["sale", "purchase", "stock"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "license": "LGPL-3",
}
