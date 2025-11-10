# MRP MTS Else MTO Parent Link Fix

## Problem

In Odoo 18, when using `mts_else_mto` (Make To Stock, else Make To Order) procurement rules for manufacturing, parent-child MO relationships are not established correctly.

### Symptoms

- Child MOs are created and visible in the Overview
- Parent/Child MO smart buttons don't show on new MOs
- Changing quantity on parent MO doesn't propagate to child MOs
- This happens specifically with `mts_else_mto` rules, not with pure `make_to_order` rules

## Root Cause

The issue is in how Odoo handles `mts_else_mto` procurement:

1. **`_adjust_procure_method()`** (stock/models/stock_move.py line 2328-2331):
   ```python
   if rule.procure_method in ['make_to_stock', 'make_to_order']:
       move.procure_method = rule.procure_method
   else:
       move.procure_method = 'make_to_stock'  # ← mts_else_mto goes here!
   ```
   Sets `move.procure_method = 'make_to_stock'` for `mts_else_mto` rules.

2. **`_action_confirm()`** (stock/models/stock_move.py line 1523-1525):
   ```python
   elif move.rule_id and move.rule_id.procure_method == 'mts_else_mto':
       move_create_proc.add(move.id)  # ← Procurement IS created
   ```
   Still creates procurement because it checks the rule's procure_method.

3. **`_prepare_procurement_values()`** (stock/models/stock_move.py line 1659):
   ```python
   if self.procure_method == "make_to_order":
       move_dest_ids = self
   ```
   Does NOT include `move_dest_ids` because it checks the move's procure_method, which is `'make_to_stock'`.

4. **Result**: Child MO created without `move_dest_ids` → no parent link.

## Solution

This module overrides `stock.move._prepare_procurement_values()` to also include `move_dest_ids` when the rule's `procure_method` is `'mts_else_mto'`:

```python
def _prepare_procurement_values(self):
    res = super()._prepare_procurement_values()
    
    if res.get('move_dest_ids'):
        return res
    
    # Also include move_dest_ids for mts_else_mto rules
    if self.rule_id and self.rule_id.procure_method == 'mts_else_mto':
        res['move_dest_ids'] = self
    
    return res
```

This ensures parent-child MO relationships work correctly with `mts_else_mto` rules.

## Installation

1. Add this module to your addons path
2. Update the module list
3. Install the module

## Testing

After installation:

1. Ensure your manufacture rules use `procure_method='mts_else_mto'`
2. Create a product with a multi-level BOM
3. Ensure components have "Manufacture" route enabled
4. Create a manufacturing order for the top-level product
5. Confirm the MO
6. Check that the "Child MO" smart button appears with the correct count
7. Click the button to verify child MOs are linked
8. Try changing the quantity on the parent MO - it should propagate to children

## Verification

Check if your rules are affected:

```python
# In Odoo shell
manu_rules = env['stock.rule'].search([('action', '=', 'manufacture')])
for rule in manu_rules:
    print(f"{rule.name}: {rule.procure_method}")
```

If you see `'mts_else_mto'`, you need this module.

## Compatibility

- Odoo 18.0
- Depends on: `mrp`, `stock`

## License

LGPL-3
