{
    "name": "Mail Company Signature",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Company-standard email signature generated from a template, "
    "with a visible signature preview in the chatter composer.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail", "hr"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/res_users_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_company_signature/static/src/**/*",
        ],
        "web.assets_tests": [
            "mail_company_signature/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
