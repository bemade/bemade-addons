# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Chatter Pinned Messages",
    "version": "19.0.1.0.1",
    "category": "Discuss",
    "summary": "Pin important notes and emails on top of any record's chatter.",
    "description": """
Chatter Pinned Messages
=======================

Odoo can pin messages in Discuss channels only. This module brings pinning to
the chatter of every record (customers, sales orders, tickets, ...).

Features
--------

* A **Pin** / **Unpin** action on notes and emails in the chatter, offered to
  internal users who can edit the record.
* A **Pinned (n)** block on top of the chatter lists the pinned messages, even
  old ones that are not in the first page of the history. Clicking one jumps to
  it in the thread; each has an **Unpin** link.
* Pinned messages keep their place in the history, with a pin marker.
* Pins are shared: everyone who can read the record sees them.
* Pinning is silent: no note is posted, nobody is notified, and the message's
  last-modified date does not change.

Scope
-----

* Only comments (notes, messages) and emails can be pinned; tracking lines and
  system notifications cannot.
* Portal and public users never see the action nor the block.
* Discuss channels keep Odoo's own pin feature, unchanged.
""",
    "author": "Bemade Inc.",
    "maintainers": ["dureposd"],
    "website": "https://www.bemade.org",
    "depends": ["mail"],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "mail_chatter_pin/static/src/**/*",
        ],
        "web.assets_tests": [
            "mail_chatter_pin/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
