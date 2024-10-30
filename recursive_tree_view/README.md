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
