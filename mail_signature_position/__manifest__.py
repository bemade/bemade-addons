{
    "name": "Mail Signature Position",
    "version": "19.0.1.0.0",
    "category": "Productivity/Discuss",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "summary": "Company setting to place the email signature above or below "
    "the quoted message on Reply All and Forward.",
    "description": """
Mail Signature Position
=======================

When a user clicks **Reply All** or **Forward** on a message in the chatter, Odoo
pre-fills the full composer with an empty typing line, the quoted message
("On ... wrote" / "Forwarded message") and then the user's signature at the very
bottom, under the quoted thread.

This module adds a per-company setting, **Settings > Discuss > Signature
Position**, with two values:

* **Below the quoted message** (default): Odoo's standard layout, unchanged.
* **Above the quoted message**: the signature is placed right under the empty
  typing line, before the "On ... wrote" reply header or the "Forwarded
  message" header, as most email clients do.

The value of the current company is sent to the web client with the user's
store data (one global value) and read by two OWL template extensions of
``mail.Message.bodyInReply`` and ``mail.Message.bodyInForward``.

Scope: only Reply All and Forward quote the thread in Odoo 19. A normal chatter
message never quotes anything, so it is not affected.
""",
    "depends": ["mail"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_signature_position/static/src/**/*",
        ],
        "web.assets_unit_tests": [
            "mail_signature_position/static/tests/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
