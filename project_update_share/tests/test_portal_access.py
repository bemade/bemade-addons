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
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

from .common import ProjectUpdateShareCommon


class TestPortalAccess(ProjectUpdateShareCommon):
    def setUp(self):
        super().setUp()
        self.internal = self._update(name="Internal")
        self.shared = self._update(
            name="Shared",
            internal_only=False,
            recipient_ids=[Command.set(self.follower.ids)],
        )

    def _readable(self, user):
        return self.env["project.update"].with_user(user).search(
            [("project_id", "=", self.project.id)]
        )

    def test_recipient_reads_only_what_is_shared_with_them(self):
        self.assertEqual(self._readable(self.follower_user), self.shared)
        as_follower = self.shared.with_user(self.follower_user)
        self.assertEqual(as_follower.name, "Shared")
        self.assertIn("Invoices now show tracking.", as_follower.description)
        self.assertEqual(as_follower.status, "on_track")

    @mute_logger("odoo.addons.base.models.ir_rule", "odoo.models")
    def test_no_access_without_being_a_recipient(self):
        # The collaborator can open the project, but was not chosen.
        self.assertFalse(self._readable(self.collaborator_user))
        self.assertFalse(self._readable(self.outsider_user))
        with self.assertRaises(AccessError):
            self.internal.with_user(self.follower_user).read(["name"])
        with self.assertRaises(AccessError):
            self.shared.with_user(self.collaborator_user).read(["name"])

    @mute_logger("odoo.addons.base.models.ir_rule", "odoo.models")
    def test_portal_cannot_write_create_or_delete(self):
        as_follower = self.shared.with_user(self.follower_user)
        with self.assertRaises(AccessError):
            as_follower.write({"name": "Mine now"})
        with self.assertRaises(AccessError):
            as_follower.unlink()
        with self.assertRaises(AccessError):
            self.env["project.update"].with_user(self.follower_user).create({
                "name": "x", "status": "on_track", "project_id": self.project.id,
            })

    def test_unsharing_and_removal_hide_at_once(self):
        other = self._update(
            name="Other",
            internal_only=False,
            recipient_ids=[Command.set(self.follower.ids)],
        )
        self.assertEqual(self._readable(self.follower_user), self.shared | other)
        self.shared.internal_only = True
        other.recipient_ids = [Command.unlink(self.follower.id)]
        self.assertFalse(self._readable(self.follower_user))

    def test_internal_users_unchanged(self):
        self.assertEqual(self._readable(self.colleague), self.internal | self.shared)
