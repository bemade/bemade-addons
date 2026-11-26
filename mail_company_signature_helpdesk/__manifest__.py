{
    "name": "Mail Company Signature - Helpdesk",
    "version": "19.0.1.0.0",
    "category": "Helpdesk",
    "summary": "Ticket emails use the ticket team's address (signature, and "
    "sender when the company asks for it), whoever writes them.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail_company_signature", "helpdesk"],
    "data": [
        "views/helpdesk_team_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "mail_company_signature_helpdesk/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
