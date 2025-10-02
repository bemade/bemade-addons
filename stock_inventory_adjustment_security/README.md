# Stock Inventory Adjustment Security

## Overview

This module adds granular security controls for inventory adjustments in Odoo. It allows you to separate the ability to **count inventory** from the ability to **apply adjustments**.

## Features

- **New Security Group**: "Inventory: Manual Adjustments"
- **Separation of Duties**: 
  - Regular inventory users can view stock and enter counted quantities
  - Only privileged users can apply the adjustments to modify actual stock levels
- **No Impact on Automatic Operations**: Stock moves from pickings, manufacturing orders, and other automatic operations work normally

## Use Case

Perfect for organizations that want to:
- Allow warehouse staff to participate in inventory counts
- Restrict who can actually modify stock levels
- Maintain audit trails by limiting adjustment privileges
- Implement proper inventory control procedures

## How It Works

### Technical Implementation

The module overrides the `write()` method on `stock.quant` to check:
1. If the operation is in "inventory mode" (manual adjustment context)
2. If the `quantity` field is being modified
3. If the user has the required security group

The check uses Odoo's built-in `_is_inventory_mode()` method which returns `True` only when:
- The `inventory_mode` context flag is set (manual adjustments)
- The user has the `stock.group_stock_user` group

### User Experience

**Regular Inventory User:**
- Can navigate to Inventory > Inventory Adjustments
- Can view current stock quantities
- Can enter counted quantities in the `inventory_quantity` field
- **Cannot** click "Apply" to commit the changes
- Receives clear error message when attempting to apply

**Privileged User (with Manual Adjustments group):**
- Can do everything a regular user can do
- **Can** click "Apply" to commit inventory adjustments
- Can modify actual stock quantities

## Configuration

1. Install the module
2. Go to Settings > Users & Companies > Users
3. Edit a user who should be able to apply inventory adjustments
4. Add them to the "Inventory: Manual Adjustments" group

## Testing

The module includes comprehensive test coverage:

```bash
# Run all tests
odoo-bin -d your_database -i stock_inventory_adjustment_security --test-enable --stop-after-init

# Run specific test class
odoo-bin -d your_database --test-tags stock_inventory_adjustment_security
```

### Test Cases

- ✅ Regular users can set inventory_quantity (count)
- ✅ Regular users cannot apply adjustments
- ✅ Privileged users can apply adjustments
- ✅ Automatic operations (pickings, etc.) are not affected
- ✅ Inventory mode detection works correctly
- ✅ Multiple quant adjustments work correctly
- ✅ Non-inventory mode writes are not restricted

## Compatibility

- Odoo 18.0
- Depends on: `stock`

## License

LGPL-3

## Author

Bemade Inc.
https://bemade.org
