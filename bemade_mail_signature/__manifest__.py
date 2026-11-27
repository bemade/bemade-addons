{
    "name": "Mail Signature: Shown as Sent",
    "version": "19.0.1.0.1",
    "category": "Productivity/Discuss",
    "summary": "Show the email signature in the composer exactly as it is sent, "
    "and keep it (folded) in the logged chatter message.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "bemade_mail_signature/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "bemade_mail_signature/static/tests/**/*",
            ("remove", "bemade_mail_signature/static/tests/tours/**/*"),
        ],
        "web.assets_tests": [
            "bemade_mail_signature/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
