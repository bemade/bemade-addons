{
    "name": "Sale Order Line Expected Ship Date",
    "version": "18.0.1.0.0",
    "category": "Sales",
    "summary": "Add expected delivery date calculation to sale order lines",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "description": """
        This module adds an expected delivery date field to sale order lines.
        The date is calculated based on the order date and lead time, or can be
        set manually to calculate the required lead time.
    """,
    "depends": ["sale_stock", "sale_purchase_late_notification"],
    "data": [
        "views/sale_order_line_views.xml",
        "report/sale_report_templates.xml",
        "views/sale_portal_templates.xml",
    ],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
