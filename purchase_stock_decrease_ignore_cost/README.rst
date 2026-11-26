========================================
Purchase Decrease Ignores Converted Cost
========================================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1| |badge2|

When the quantity of a confirmed purchase order line is lowered, Odoo creates a
negative stock move and nets it against the open receipt. It only nets moves
that share the same unit cost in the company currency. On an order in a foreign
currency, that cost is converted at the rate loaded when the quantity is
changed. If a new rate was loaded since the order was confirmed, the costs
differ by a cent, the receipt keeps its full quantity, and Odoo creates a
return to the vendor for the decrease instead.

With this module enabled, a purchase line decrease nets against the open
receipt moves of the same line whatever their cost, and each remaining receipt
move keeps its original unit cost. Without it, Odoo would replace that cost
with a weighted average of the two costs, which can be far off when little
quantity remains.

Only negative moves that come from a purchase order line are affected. Moves
already received are never touched, and lowering a line below the received
quantity is still refused, as in standard Odoo.

**Table of contents**

.. contents::
   :local:

Configuration
=============

The module does nothing until it is enabled, per company:

1. Go to Purchase > Configuration > Settings.
2. Under Orders, enable "Reduce Receipts Regardless of Cost".
3. Save.

Usage
=====

Lower the quantity of a confirmed purchase order line, or set it to 0. The
open receipt is reduced (or its move cancelled) instead of a return being
created, even if the exchange rate changed since the order was confirmed.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/bemade/bemade-addons/issues>`_.
In case of trouble, please check there if your issue has already been reported.

Credits
=======

Authors
~~~~~~~

* Bemade Inc.

Contributors
~~~~~~~~~~~~

* Marc Durepos <marc@bemade.org>

Maintainers
~~~~~~~~~~~

This module is maintained by Bemade Inc.
