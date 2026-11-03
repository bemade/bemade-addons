# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: a portal user sees the updates shared with them, and only those.

ACCEPTANCE CRITERIA
- A portal user can read an update through the ORM as themselves (no sudo)
  if and only if it is shared (Internal only unticked) AND their partner
  (``user.partner_id``) is among its recipients.
- They cannot read an internal update, nor a shared update they are not a
  recipient of (even on a project they can open), nor create, write or
  delete any update.
- Ticking Internal only, or removing them from the recipients, makes the
  update unreadable to them immediately.
- Internal users' access to updates is unchanged from core Odoo.
"""
