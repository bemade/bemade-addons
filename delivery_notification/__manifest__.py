{
    "name": "Delivery Notification",
    "version": "18.0.1.0.0",
    "category": "Inventory/Delivery",
    "summary": "Automatically notify customers of tracking numbers on sales orders",
    "description": """
        This module automatically posts a message to the sales order
        when a tracking number is added to a delivery order.
        
        The message includes:
        - The shipping method
        - The tracking number
        - A tracking link (if available from the carrier)
        - The client's PO number for reference
        
        All followers of the sale order (including the customer if they have an email)
        will be notified automatically.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": [
        "sale",
        "sale_stock",
        "delivery",
        "stock",
    ],
    "data": [
        "data/mail_subtype.xml",
        "data/mail_template.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
