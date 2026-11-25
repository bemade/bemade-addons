"""Pinning from the chatter in a real browser.

Acceptance criteria:

1.  On a contact's chatter, an internal user who can edit it pins a note from
    the message actions; a "Pinned (1)" block appears on top of the chatter and
    the note keeps its place in the history with a pin marker.
2.  Unpinning from the block removes the block and the marker.
3.  A user who can read but not edit the record sees the block, but neither
    the Unpin link nor the Pin/Unpin message action.
4.  The server state matches the clicks (the note ends unpinned), and no
    message was posted on the record.
5.  Two messages pinned in the same second (equal ``pinned_at``) both show in
    a "Pinned (2)" block; the page does not freeze sorting them.
6.  The 2-line preview separates paragraphs, block elements and line breaks
    with a space instead of running the words together.
"""

from markupsafe import Markup

from odoo.fields import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestChatterPinTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Tours run as admin: sibling addons add fields to the contact form
        # that a minimal internal user may not read, which breaks the form.
        cls.admin = cls.env.ref("base.user_admin")
        cls.partner = cls.env["res.partner"].create({"name": "Pin Tour Company"})
        cls.note = cls.partner.message_post(
            body="Synthetic tour note",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def test_chatter_pin_tour(self):
        messages_before = self.partner.message_ids
        self.start_tour(
            "/odoo/res.partner/%s" % self.partner.id,
            "mail_chatter_pin_tour",
            login="admin",
        )
        self.env.invalidate_all()
        self.assertFalse(self.note.pinned_at, "the tour unpinned the note at the end")
        self.assertEqual(self.partner.message_ids, messages_before)

    def test_chatter_pin_readonly_tour(self):
        readonly_group = self.env["res.groups"].create({"name": "Pin tour read-only"})
        self.env["ir.rule"].create(
            {
                "name": "pin tour: no partner write",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "domain_force": "[(0, '=', 1)]",
                "groups": [Command.link(readonly_group.id)],
                "perm_read": False,
                "perm_create": False,
                "perm_write": True,
                "perm_unlink": False,
            }
        )
        self.admin.group_ids = [Command.link(readonly_group.id)]
        self.assertFalse(self.partner.with_user(self.admin).has_access("write"))
        self.partner.message_set_pin(self.note.id, True)
        self.start_tour(
            "/odoo/res.partner/%s" % self.partner.id,
            "mail_chatter_pin_readonly_tour",
            login="admin",
        )
        self.env.invalidate_all()
        self.assertTrue(self.note.pinned_at)

    def _pin_at(self, messages, pinned_at):
        """Set ``pinned_at`` straight in SQL, like core does when pinning."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE mail_message SET pinned_at = %s WHERE id IN %s",
            (pinned_at, tuple(messages.ids)),
        )
        messages.invalidate_recordset(["pinned_at"])

    def test_chatter_pin_same_second_tour(self):
        first = self.partner.message_post(
            body="Synthetic first pin",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        second = self.partner.message_post(
            body="Synthetic second pin",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self._pin_at(first | second, "2026-01-15 10:20:30")
        self.start_tour(
            "/odoo/res.partner/%s" % self.partner.id,
            "mail_chatter_pin_same_second_tour",
            login="admin",
        )

    def test_chatter_pin_preview_tour(self):
        message = self.partner.message_post(
            body=Markup(
                "<p>Thanks for the order.</p><p>Could you confirm the date?</p>"
                "<div>Example Corp</div><div>100 Sample Street</div>"
                "<p>Line one<br>Line two</p>"
            ),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self._pin_at(message, "2026-01-15 10:20:30")
        self.start_tour(
            "/odoo/res.partner/%s" % self.partner.id,
            "mail_chatter_pin_preview_tour",
            login="admin",
        )
