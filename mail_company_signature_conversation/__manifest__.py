{
    "name": "Mail Company Signature - Conversations",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Conversation replies record the mailbox they were really sent "
    "from, with « Send from the signature address » on.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["conversation_base", "mail_company_signature"],
    "assets": {
        "web.assets_tests": [
            "mail_company_signature_conversation/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": True,
}
