Bridge module between `product_uom_factor` and `sale`.

When a sale order line uses a cross-category UoM (e.g. ordering in "Bag" when
the product is stocked in "lb"), this module computes and surfaces the
base-UoM equivalent quantity so users can verify conversions at a glance.

## Features

- Adds a computed **Base UoM** helper column on the SO line list (shows
  `"= 250.00 lb"` for internal users; column is optional/show by default).
- Injects a grey base-UoM quantity note under the product name in the
  **sale order / quotation PDF** (customer-facing; shows only the quantity,
  e.g. `"250.00 lb"`, without the equation form).

## Dependencies

Requires `product_uom_factor` (core) and `sale`.
