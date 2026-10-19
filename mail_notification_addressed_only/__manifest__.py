{
    "name": "Mail Notification: Email Only When Addressed",
    "version": "19.0.1.0.1",
    "category": "Discuss",
    "summary": "Internal followers get chatter emails only when addressed; "
    "everything else lands in their Odoo inbox.",
    "description": """
Lets an administrator choose which record types (models) stop flooding
internal followers' mailboxes. On a listed model, an internal user who follows
a record but is not addressed by a message (not a recipient, not mentioned,
not in Cc/Bcc) receives an in-app (inbox) notification instead of an email.
Customers, portal users and other external recipients keep receiving emails
exactly as in standard Odoo. Unlisted models are never affected.

Installing the module is the opt-in: it lists sales orders, tasks, helpdesk
tickets and accounting entries by default. Nothing changes for models removed
from the list in Settings > Discuss.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "mail_notification_addressed_only/static/tests/tours/addressed_only_settings.steps.js",
            "mail_notification_addressed_only/static/tests/tours/addressed_only_settings.tour.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
