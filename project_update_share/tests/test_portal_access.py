# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: portal users see shared updates, and only those.

ACCEPTANCE CRITERIA
- A portal user who can open a project (follower of a portal-visible
  project, or collaborator) can read its Shared updates through the ORM as
  themselves (no sudo): title, date, status, description.
- The same user cannot read its Internal updates, nor any update of a
  project they cannot open, nor create, write or delete any update.
- An update made Internal again is unreadable to them immediately.
- Internal users' access to updates is unchanged from core Odoo.
"""
