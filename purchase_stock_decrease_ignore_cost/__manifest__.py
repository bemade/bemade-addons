# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

{
    "name": "Purchase Decrease Ignores Converted Cost",
    "version": "18.0.1.0.0",
    "category": "Inventory/Purchase",
    "summary": "Lowering a confirmed foreign-currency PO line reduces the open "
    "receipt even when the exchange rate changed since confirmation",
    "author": "Bemade Inc.",
    "maintainers": ["mdurepos"],
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["purchase_stock"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "application": False,
}
