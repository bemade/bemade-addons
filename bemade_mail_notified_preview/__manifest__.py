# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Mail: Preview Notified Followers",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Show, under the recipients, which followers a message will also reach.",
    "description": """
Preview Notified Followers
==========================

When a message is sent from a record, Odoo also notifies every active follower
subscribed to *Discussions*. Both composers only hint at it with a "Followers
only" placeholder while the *To* field is empty, and say nothing once a
recipient is typed. This module makes the reality visible.

Features
--------

* One read-only line under the recipients of the chatter's **Send message**
  composer and of the full composer (after the Cc/Bcc rows when the OCA module
  ``mail_composer_cc_bcc`` is installed)::

    Also sent to followers: A, B (email) · C (Odoo inbox) · ⚠ D (no email — won't receive)

  or "No followers will be notified".
* Computed from the same data as the send path
  (``mail.followers._get_recipient_data``): active followers subscribed to the
  message's subtype, minus the sender and the partners already in To/Cc/Bcc.
* Followers who get the message in their Odoo inbox are told apart from those
  who get an email; a follower to be emailed who has no valid email address is
  flagged, since nothing will reach them.

Scope
-----

* Display only: it never changes who is notified.
* Single-record messages only; not shown for log notes, mass mailing or batch
  sending.
* Shown only to users who can read the record (and therefore its followers).
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "depends": ["mail"],
    "data": [
        "wizard/mail_compose_message_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "bemade_mail_notified_preview/static/src/**/*",
        ],
        "web.assets_tests": [
            "bemade_mail_notified_preview/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
