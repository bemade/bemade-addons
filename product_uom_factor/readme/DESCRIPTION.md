Odoo 19.0 allows adding UoMs from any category to a product's "Packagings"
(`uom_ids` field), enabling users to sell or purchase in units from a different
category than the product's base UoM (e.g., selling ink by the millilitre when
it is stocked by count as pails).

However, cross-category quantities require a product-specific conversion factor
(e.g. 1 pail = 20 000 mL) that Odoo's standard UoM system does not provide —
standard factors are relative to the category reference unit, not to the product.

This module introduces `product.uom.factor`, a **delegation model**
(`_inherits = {'uom.uom': 'delegate_uom_id'}`). Each factor row creates a real
`uom.uom` record grafted into the product's base-UoM tree (`relative_uom_id` =
base UoM, `relative_factor` = the factor), making it intra-tree with the base.
Core `_compute_quantity()` and `_compute_price()` then resolve the conversion
natively everywhere — stock, MRP, purchase, sale, valuation, and PDF reports —
with no patching. Scoping is enforced by completing Odoo's own `allowed_uom_ids`
pattern: factor-UoMs are added to `product.uom_ids` so they appear in each
line's dropdown, and an `@api.constrains` on the line scoping mixin rejects a
wrong cross-tree UoM selection at save with a clear `ValidationError`.

## Bridge modules

Two optional bridge modules extend this core with order-side display helpers:

- **product_uom_factor_sale** — adds a computed "Base UoM" helper column on SO
  lines and injects the base-UoM quantity as a grey note in the sale order PDF
  report (e.g. "250 lb" under the product name).
- **product_uom_factor_purchase** — mirrors the sale bridge for PO lines and
  the purchase order / quotation PDF reports.

Install the bridge modules alongside this one to expose the display helpers.
The core module remains pure product-side (no sale/purchase dependency).
