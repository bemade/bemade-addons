"""Which followers a Discussions message on one record will also reach.

Acceptance criteria:

1.  A follower subscribed to Discussions is listed; a follower who is not
    subscribed to Discussions (e.g. only to notes or another subtype) is not.
2.  An internal user who reads notifications in Odoo is marked ``inbox``; one
    who reads them by email, and an external contact, are marked ``email``.
3.  The current user (the author) is never listed, even when following.
4.  A partner passed in ``exclude_partner_ids`` (already in To/Cc) is not
    listed.
5.  A follower to be emailed who has no valid email address is listed with
    ``has_email`` False.
6.  An archived partner who still follows is not listed.
7.  The list matches what ``message_post`` actually notifies on the same
    record (same partners) - the preview never diverges from the send path.
8.  The public wrapper requires read access on the record and returns the
    rendered line; the line reads "No followers will be notified" when nobody
    else is reached.
9.  The rendered line groups email, Odoo inbox and no-email followers.
"""

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install")
class TestNotifiedPreviewFollowers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.mt_comment = cls.env.ref("mail.mt_comment")
        cls.mt_note = cls.env.ref("mail.mt_note")
        cls.sender = new_test_user(
            cls.env,
            login="preview_sender",
            name="Sample Sender",
            email="sender@example.com",
            groups="base.group_user,base.group_partner_manager",
        )
        cls.user_inbox = new_test_user(
            cls.env,
            login="preview_inbox",
            name="Alice Inbox",
            email="alice@example.com",
            notification_type="inbox",
        )
        cls.user_email = new_test_user(
            cls.env,
            login="preview_email",
            name="Bob Email",
            email="bob@example.com",
            notification_type="email",
        )
        Partner = cls.env["res.partner"]
        cls.contact = Partner.create({"name": "Carol Contact", "email": "carol@example.com"})
        cls.no_email = Partner.create({"name": "Dan Noemail"})
        cls.bad_email = Partner.create({"name": "Erin Bademail", "email": "not-an-email"})
        cls.not_subscribed = Partner.create(
            {"name": "Frank Notes", "email": "frank@example.com"}
        )
        cls.archived = Partner.create({"name": "Gina Archived", "email": "gina@example.com"})
        cls.record = Partner.create({"name": "Sample Customer Co"})
        cls.record.message_unsubscribe(partner_ids=cls.record.message_partner_ids.ids)
        cls.record.message_subscribe(
            partner_ids=(
                cls.sender.partner_id
                | cls.user_inbox.partner_id
                | cls.user_email.partner_id
                | cls.contact
                | cls.no_email
                | cls.bad_email
                | cls.archived
            ).ids,
            subtype_ids=cls.mt_comment.ids,
        )
        cls.record.message_subscribe(
            partner_ids=cls.not_subscribed.ids, subtype_ids=cls.mt_note.ids
        )
        cls.archived.active = False

    def _preview(self, **kwargs):
        record = self.record.with_user(self.sender)
        return {f["id"]: f for f in record._notified_preview_followers(**kwargs)}

    def test_subscribed_vs_not(self):
        preview = self._preview()
        self.assertIn(self.contact.id, preview)
        self.assertNotIn(self.not_subscribed.id, preview)

    def test_inbox_vs_email(self):
        preview = self._preview()
        self.assertEqual(preview[self.user_inbox.partner_id.id]["notif"], "inbox")
        self.assertEqual(preview[self.user_email.partner_id.id]["notif"], "email")
        self.assertEqual(preview[self.contact.id]["notif"], "email")
        self.assertEqual(preview[self.contact.id]["name"], "Carol Contact")
        self.assertTrue(preview[self.contact.id]["has_email"])

    def test_author_excluded(self):
        self.assertNotIn(self.sender.partner_id.id, self._preview())

    def test_partner_in_to_excluded(self):
        preview = self._preview(exclude_partner_ids=[self.contact.id, self.no_email.id])
        self.assertNotIn(self.contact.id, preview)
        self.assertNotIn(self.no_email.id, preview)
        self.assertIn(self.user_email.partner_id.id, preview)

    def test_follower_without_email_flagged(self):
        preview = self._preview()
        self.assertFalse(preview[self.no_email.id]["has_email"])
        self.assertFalse(preview[self.bad_email.id]["has_email"])

    def test_archived_partner_excluded(self):
        self.assertNotIn(self.archived.id, self._preview())

    def test_preview_matches_send_path(self):
        expected = set(self._preview(exclude_partner_ids=[self.contact.id]))
        message = self.record.with_user(self.sender).message_post(
            body="Synthetic message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=[self.contact.id],
        )
        notified = set(message.notification_ids.res_partner_id.ids) - {self.contact.id}
        self.assertEqual(notified, expected)

    def test_public_wrapper_requires_read_access(self):
        blind_group = self.env["res.groups"].create({"name": "Preview blind group"})
        self.env["ir.rule"].create(
            {
                "name": "preview: cannot read the sample record",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "domain_force": "[('id', '!=', %d)]" % self.record.id,
                "groups": [Command.link(blind_group.id)],
                "perm_read": True,
                "perm_write": False,
                "perm_create": False,
                "perm_unlink": False,
            }
        )
        blind = new_test_user(self.env, login="preview_blind", groups="base.group_user")
        blind.group_ids = [Command.link(blind_group.id)]
        with mute_logger("odoo.models", "odoo.addons.base.models.ir_rule"):
            with self.assertRaises(AccessError):
                self.record.with_user(blind).get_notified_preview()

    def test_public_wrapper_line_none(self):
        lonely = self.env["res.partner"].create({"name": "Lonely Record"})
        lonely.message_unsubscribe(partner_ids=lonely.message_partner_ids.ids)
        res = lonely.with_user(self.sender).get_notified_preview()
        self.assertEqual(res["followers"], [])
        self.assertEqual(res["line"], "No followers will be notified")
        self.assertFalse(res["warn"])

    def test_public_wrapper_line_groups(self):
        res = self.record.with_user(self.sender).get_notified_preview(
            exclude_partner_ids=[self.bad_email.id]
        )
        self.assertEqual(
            res["line"],
            "Also sent to followers: Bob Email, Carol Contact (email)"
            " · Alice Inbox (Odoo inbox)"
            " · ⚠ Dan Noemail (no email — won't receive)",
        )
        self.assertTrue(res["warn"])
