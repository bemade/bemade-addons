# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Project Update Share",
    "version": "19.0.1.0.0",
    "category": "Services/Project",
    "summary": "Share a project update with the client, by email and on the portal",
    "description": """
Project Update Share
====================

Core Odoo never sends a project update to anyone: creating one only logs an
internal note on the update. This module lets a project manager share an
update with the client, by email and on the portal, one update at a time.

Visibility
----------
* Each update is **Internal** (default) or **Shared with client**.
* Internal updates behave exactly as in core Odoo. Nothing is sent and
  nothing appears on the portal. Updates created by code stay internal unless
  that code asks otherwise.

Sharing
-------
* Sharing an update asks for its **recipients**, prefilled with the project's
  followers and its portal collaborators and editable before sending.
* The update is posted once to the project's chatter as a Discussion message
  addressed to those recipients. The message carries the title, status and
  full content, and links to the project's updates page on the portal.
* Editing a shared update does not send it again.
* Switching a shared update back to Internal removes it from the portal at
  once. The email already sent cannot be recalled.

Portal
------
* ``/my/projects/<id>/updates`` lists the project's shared updates, newest
  first, with date, status and content.
* An **Updates** button reaches it from the top of the project's portal page
  and from the Project Sharing view that collaborators see.
* Portal users can read shared updates only, and only on projects they can
  already open. Internal updates are never visible.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["project", "portal"],
    "data": [],
    "installable": True,
    "application": False,
}
