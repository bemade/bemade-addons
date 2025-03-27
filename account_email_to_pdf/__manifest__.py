{
    "name": "Account Email to PDF",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "summary": "Convert email messages to PDF attachments for vendor bills",
    "description": """
Account Email to PDF
====================
This module converts email messages without attachments into PDF attachments
when processing incoming emails for vendor bills.

Instead of rejecting emails without attachments, the system will create a PDF
from the email content and attach it to the message, allowing the vendor bill
creation process to continue.
    """,
    "author": "Bemade",
    "website": "https://bemade.org",
    "depends": ["account", "mail"],
    "data": [],
    "installable": True,
    "auto_install": False,
    "license": "LGPL-3",
}
