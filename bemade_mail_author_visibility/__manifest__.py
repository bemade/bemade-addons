# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Mail Author Visibility",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": (
        "Injects a 'Posted by:' author header block into chatter notification "
        "emails so recipients immediately know who posted each message."
    ),
    "author": "Bemade Inc.",
    "maintainers": ["mdurepos"],
    "website": "https://www.bemade.org",
    "depends": ["mail"],
    "data": [
        "views/mail_notification_layout.xml",
    ],
    "auto_install": ["mail"],
    "installable": True,
    "license": "LGPL-3",
}
