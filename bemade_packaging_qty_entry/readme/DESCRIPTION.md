Extends `product_uom_packaging` so that the **package count is the primary
quantity entered** on both purchase and sale order lines.

When a packaging is selected on a line, the user types how many packages they
want (**# Packages**). The base stocking-UoM quantity (`product_qty` on PO,
`product_uom_qty` on SO) is derived automatically via a stored inverse:

```
base_qty = packaging.qty × package_count  (converted to the line UoM)
```

The forward compute (base → packages, `ceil`) is retained so the package
column accurately reflects reality when the base qty is edited directly.

**View changes:** the packaging columns (packaging type + package qty) are moved
**before** the base qty column so the natural entry order is
packaging → packages → (optional) base qty.
