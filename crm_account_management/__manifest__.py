{
    "name": "CRM Account Management",
    "version": "18.0.4.0.0",
    "category": "Sales/CRM",
    "summary": "Customer Account Management with Dashboard and Reporting",
    "description": """
CRM Account Management
======================

Provides organizational unit (customer account) functionality for enhanced
account visibility:

- Customer Account Dashboard with YTD metrics
- Buying trends and top products analysis
- Account-level chatter
- Annual review PDF report
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "account",
        "sale",
        "sale_stock",
        "crm",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/init_data.xml",
        "data/cron.xml",
        "views/organizational_unit_views.xml",
        "views/res_partner_views.xml",
        "views/menu.xml",
        "report/annual_review_report.xml",
        "report/annual_review_template.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "crm_account_management/static/src/js/buying_trends_widget.js",
            "crm_account_management/static/src/xml/buying_trends_widget.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
