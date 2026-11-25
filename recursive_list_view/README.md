# Recursive Tree View

Bemade Inc.

Copyright (C) 2023-June Bemade Inc. ([https://www.bemade.org](https://www.bemade.org)).
Author: Marc Durepos (Contact : [marc@bemade.org](mailto\:marc@bemade.org))

This program is under the terms of the GNU Lesser General Public License (LGPL-3).
For details, visit [https://www.gnu.org/licenses/lgpl-3.0.en.html](https://www.gnu.org/licenses/lgpl-3.0.en.html)

## Overview

The Recursive Tree View module for Odoo allows users to easily visualize hierarchical data structures in Odoo list (tree) views. With this module, you can mark a tree view as recursive, enabling the expansion of descendants of a parent record in a seamless and user-friendly way.

## Features

- Expand and collapse descendants directly in tree views.
- Mark specific tree views as recursive to represent hierarchical data structures.
- Enhance the visualization of complex relationships, making it easier to navigate and understand.

## Configuration

1. Install the module in Odoo.
2. Configure the desired tree views to be recursive by modifying the view definition. Simply add the attribute recursive="1" (or true or True) to the tree element.

### Depth cap: `recursive_depth`

`recursive_depth="N"` limits how many levels the list shows, its own rows being
level 1. With `recursive_depth="2"`, the rows unfold to their children, and those
children have no expand button. Without it (or with `0`), every level can be
unfolded.

### Lists embedded in a form (x2many)

`recursive` also works on a list embedded in a form, e.g. a `child_ids` field:

```xml
<field name="child_ids">
    <list editable="bottom" recursive="1" recursive_depth="2">
        <field name="name"/>
    </list>
</field>
```

- On an embedded list, `recursive` may be a python expression evaluated on the
  parent (form) record, to make the list recursive only on some records, e.g.
  `recursive="not parent_id"`. The fields used must be in the form.
- The list's own rows behave as usual (inline edit, add a line, reorder, delete).
- The unfolded rows are not part of the field's value: they are read-only, cannot
  be dragged or deleted, and clicking one opens its form.
- Unfolded rows stay unfolded when the list reloads (e.g. after saving the form).

## Usage

1. Navigate to the model with the hierarchical structure (e.g., organizational units, product categories).
2. Expand a parent record in the tree view to visualize its descendants.
3. Use the expand/collapse functionality to navigate the entire hierarchy.

## Technical Details

- The module extends the `tree` view type to add recursive behavior, 
  allowing descendants to be dynamically loaded and displayed.
- This feature is particularly useful for models that represent hierarchical relationships, such as categories, organizational units, or nested tasks.
- The module uses the field specified by `_parent_name` on the model, which is `parent_id` by default.

## License

This program is under the terms of the GNU Lesser General Public License (LGPL-3).
For details, visit [https://www.gnu.org/licenses/lgpl-3.0.en.html](https://www.gnu.org/licenses/lgpl-3.0.en.html)
