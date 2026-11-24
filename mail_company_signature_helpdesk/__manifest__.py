{
    "name": "Mail Company Signature - Helpdesk",
    "version": "19.0.1.0.0",
    "category": "Helpdesk",
    "summary": "Ticket emails show the ticket team's address in the signature, "
    "whoever writes them.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail_company_signature", "helpdesk"],
    "data": [
        "views/helpdesk_team_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": True,
}
