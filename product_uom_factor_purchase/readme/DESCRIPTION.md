Bridge module between `product_uom_factor` and `purchase`.

When a purchase order line uses a cross-category UoM (e.g. ordering in "Bag"
when the product is stocked in "lb"), this module computes and surfaces the
base-UoM equivalent quantity so buyers can verify conversions at a glance.

## Features

- Adds a computed **Base UoM** helper column on the PO line list (shows
  `"= 150.00 lb"` for internal users; column is optional/show by default).
- Injects a grey base-UoM quantity note under the product name in both the
  **purchase order PDF** (confirmed PO) and the **purchase quotation PDF**
  (RFQ). Shows only the quantity (e.g. `"150.00 lb"`), without the equation.

## Dependencies

Requires `product_uom_factor` (core) and `purchase`.
