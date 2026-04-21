# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Mail Follower CC Header",
    "version": "18.0.2.0.0",
    "category": "Discuss",
    "summary": (
        "Adds all notification recipients (minus the author) to the Cc header "
        "of outgoing notification emails — display only, SMTP envelope stays per-recipient."
    ),
    "author": "Bemade Inc.",
    "maintainers": ["mdurepos"],
    "website": "https://www.bemade.org",
    "depends": [
        "mail",
        "mail_composer_cc_bcc",
    ],
    "data": [],
    "auto_install": False,
    "installable": True,
    "license": "LGPL-3",
}
