{
    "name": "Stock Inventory Adjustment Security",
    "author": "Bemade Inc.",
    "version": "18.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Restrict manual inventory adjustments to privileged users",
    "description": """
Stock Inventory Adjustment Security
====================================

This module adds an additional security layer for inventory adjustments:

* Creates a new security group "Inventory: Manual Adjustments"
* Regular inventory users can view and count inventory (set inventory_quantity)
* Only users in the privileged group can apply adjustments (modify actual quantity)
* Automatic stock operations (pickings, manufacturing, etc.) are not affected

This allows inventory staff to participate in counts while restricting who can
actually apply the adjustments and modify stock levels.
    """,
    "website": "https://www.bemade.org",
    "depends": ["stock"],
    "data": [
        "security/security.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
    "application": False,
}
