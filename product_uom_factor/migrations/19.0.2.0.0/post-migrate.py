# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""No-op migration for product_uom_factor 19.0.2.0.0.

This version bump documents the architectural split introduced in this release:
sale-side and purchase-side display logic (computed fields, view helpers, and
PDF report injections) have been moved into the new bridge modules:

  - product_uom_factor_sale   (depends: product_uom_factor, sale)
  - product_uom_factor_purchase (depends: product_uom_factor, purchase)

The core module remains pure product-side (depends: product only) and is not
affected by this split. No schema changes, no data migrations.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info(
        "product_uom_factor upgraded to 19.0.2.0.0: "
        "sale/purchase display logic now lives in bridge modules "
        "product_uom_factor_sale and product_uom_factor_purchase."
    )
