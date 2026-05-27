Odoo 19.0 allows adding UoMs from any category to a product's "Packagings"
(`uom_ids` field), enabling users to sell or purchase in units from a different
category than the product's base UoM (e.g., selling ink by the liter when it is
stocked by weight in grams).

However, Odoo's `_compute_quantity()` and `_compute_price()` methods on `uom.uom`
no longer enforce that the source and destination UoMs belong to the same category.
When converting between UoMs of different categories, the conversion silently
produces incorrect results — typically a 1:1 ratio between base units of their
respective categories — because the standard UoM factor is relative to the
category's reference unit, not to the product.

This module adds a **conversion factor** field to the `product.uom` model (the
per-product/per-UoM link table). This factor represents the product-specific
relationship between the product's base UoM and the cross-category UoM. For
example, an ink product stocked in grams with a density of 1.05 g/mL would have
a factor of 1.05 on its liter packaging UoM, meaning 1 liter = 1050 grams.

The module overrides `_compute_quantity()` and `_compute_price()` so that when a
product is available in context, cross-category conversions use the product-specific
factor instead of producing potentially incoherent results.

## Bridge modules

Two optional bridge modules extend this core with order-side display helpers:

- **product_uom_factor_sale** — adds a computed "Base UoM" helper column on SO
  lines and injects the base-UoM quantity as a grey note in the sale order PDF
  report (e.g. "250 lb" under the product name).
- **product_uom_factor_purchase** — mirrors the sale bridge for PO lines and
  the purchase order / quotation PDF reports.

Install the bridge modules alongside this one to expose the display helpers.
The core module remains pure product-side (no sale/purchase dependency).
