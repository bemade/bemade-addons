# -*- coding: utf-8 -*-
{
    "name": "Lost Messages Routing - UX Improvements",
    "version": "18.0.1.0.0",
    "category": "Discuss",
    "summary": "Subcategories, batch actions and triage wizards for lost messages",
    "description": """
Enhanced UX for managing lost messages:

1. **Subcategories**: Classify messages (spam, bounce, auto-reply, finance, etc.)
2. **Batch Actions**: Categorize or delete multiple messages at once
3. **Triage Wizards**: 
   - Invalid Address Notification
   - Finance Triage (helpdesk ticket or forward)
    """,
    "author": "Bemade Inc.",
    "website": "https://bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail_manual_routing",
        "mail_manual_routing_fix",
        "mail_loop_prevention",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/lost_message_subcategory_data.xml",
        "views/lost_message_subcategory_views.xml",
        "views/mail_message_views.xml",
        "wizards/mail_categorize_wizard_views.xml",
        "wizards/mail_invalid_address_wizard_views.xml",
        "wizards/mail_finance_triage_wizard_views.xml",
        "views/menus.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
}
