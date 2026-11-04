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
update with chosen recipients, by email and on the portal.

Internal or shared
------------------
* **Internal only** is ticked on every new update, and an internal update
  behaves exactly as in core Odoo: nothing is sent, and no portal user sees
  it. Updates created by code stay internal unless that code says otherwise.
* Unticking it shows the update's **recipients**, prefilled with the
  project's followers and its portal collaborators, editable before saving.
  Sharing, unsharing and choosing recipients happen in the same create or
  save as the rest of the update.

Email
-----
* Each recipient is emailed once, the first time the update is shared with
  them, by a Discussion message on the project's chatter addressed to them.
  It carries the update's title, status, date and full content, and a link
  to the project's updates page on the portal.
* Adding a recipient to a shared update emails only that recipient. Editing
  the update, removing recipients or making it internal again sends nothing.
  An email already sent cannot be recalled.

Portal
------
* A portal user sees an update only if it is shared **and** they are one of
  its recipients. Making it internal again, or removing them from the
  recipients, hides it from them at once.
* ``/my/projects/<id>/updates`` lists the updates of a project shared with
  the visitor, newest first, with date, status and content.
* An **Updates** button reaches it from the top of the project's portal page
  and from the Project Sharing view that collaborators see.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["project", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "security/project_update_share_security.xml",
        "views/project_update_views.xml",
        "views/portal_templates.xml",
    ],
    "assets": {
        "project.webclient": [
            "project_update_share/static/src/project_sharing/**/*",
        ],
        "web.assets_tests": [
            "project_update_share/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
