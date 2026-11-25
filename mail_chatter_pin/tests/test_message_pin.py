"""Pinning a message on a record's chatter (server side).

Acceptance criteria:

1.  An internal user with write access to a record can pin, then unpin, a note
    or an email posted on that record; ``pinned_at`` is set, then cleared.
2.  A user who can read but not write the record is refused (AccessError).
3.  Tracking lines, system notifications and user notifications cannot be
    pinned (UserError), nor can an empty message.
4.  A message of another record cannot be pinned through this record.
5.  Discuss channels are not handled here: ``message_set_pin`` refuses them, and
    the core ``set_message_pin`` keeps working and posting its own notice.
6.  Pinning is silent: no message is posted on the record.
7.  Pinning does not move the message's ``write_date``.
8.  Loading the chatter thread data with ``pinnedMessages`` returns the pinned
    messages of the record, also when they are older than the first page.
"""

from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tests import new_test_user, tagged
from odoo.tests.common import TransactionCase
from odoo.tools.misc import mute_logger

from odoo.addons.mail.tools.discuss import Store


@tagged("post_install", "-at_install")
class TestMessagePin(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, mail_create_nolog=True))
        cls.editor = new_test_user(
            cls.env,
            login="pin_editor",
            groups="base.group_user,base.group_partner_manager",
        )
        cls.partner = cls.env["res.partner"].create({"name": "Pin Test Company"})
        cls.other_partner = cls.env["res.partner"].create({"name": "Pin Other Co"})
        cls.note = cls.partner.message_post(
            body="Synthetic important note",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        cls.email = cls.partner.message_post(
            body="Synthetic incoming email",
            message_type="email",
            subtype_xmlid="mail.mt_comment",
        )
        cls.other_note = cls.other_partner.message_post(
            body="Note on another record",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def setUp(self):
        super().setUp()
        self.env.invalidate_all()

    def _pin(self, message, pinned=True, user=None, record=None):
        record = record or self.partner
        return record.with_user(user or self.editor).message_set_pin(
            message.id, pinned
        )

    # 1
    def test_pin_and_unpin_note(self):
        self._pin(self.note)
        self.assertTrue(self.note.pinned_at)
        self._pin(self.note, pinned=False)
        self.assertFalse(self.note.pinned_at)

    def test_pin_email(self):
        self._pin(self.email)
        self.assertTrue(self.email.pinned_at)

    def test_pin_returns_store_data(self):
        res = self._pin(self.note)
        messages = res["mail.message"]
        self.assertEqual(messages[0]["id"], self.note.id)
        self.assertTrue(messages[0]["pinned_at"])

    def test_pin_twice_keeps_first_date(self):
        self._pin(self.note)
        self.env.cr.execute(
            "UPDATE mail_message SET pinned_at = pinned_at - interval '1 day' "
            "WHERE id = %s",
            (self.note.id,),
        )
        self.env.invalidate_all()
        first = self.note.pinned_at
        self._pin(self.note)
        self.assertEqual(self.note.pinned_at, first)

    # 2
    def test_read_only_user_refused(self):
        reader = new_test_user(self.env, login="pin_reader", groups="base.group_user")
        # Internal users can read partners; make this one read-only on them.
        self.env["ir.rule"].create(
            {
                "name": "pin test: no partner write",
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "domain_force": "[(0, '=', 1)]",
                "groups": [(4, self.env.ref("base.group_user").id)],
                "perm_read": False,
                "perm_create": False,
                "perm_write": True,
                "perm_unlink": False,
            }
        )
        self.partner.with_user(reader).check_access("read")
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self._pin(self.note, user=reader)
        self.assertFalse(self.note.pinned_at)

    def test_portal_user_refused(self):
        portal = new_test_user(self.env, login="pin_portal", groups="base.group_portal")
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            self._pin(self.note, user=portal)
        self.assertFalse(self.note.pinned_at)

    # 3
    def test_notification_refused(self):
        notification = self.partner.message_post(
            body="System notice", message_type="notification"
        )
        with self.assertRaises(UserError):
            self._pin(notification)
        self.assertFalse(notification.pinned_at)

    def test_user_notification_refused(self):
        message = self.env["mail.message"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "body": "Direct notification",
                "message_type": "user_notification",
            }
        )
        with self.assertRaises(UserError):
            self._pin(message)

    def test_tracking_refused(self):
        tracking = self.env["mail.message"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "body": "",
                "message_type": "notification",
                "tracking_value_ids": [
                    Command.create(
                        {
                            "field_id": self.env["ir.model.fields"]._get(
                                "res.partner", "email"
                            ).id,
                            "old_value_char": "old@example.com",
                            "new_value_char": "new@example.com",
                        }
                    )
                ],
            }
        )
        with self.assertRaises(UserError):
            self._pin(tracking)
        self.assertFalse(tracking.pinned_at)

    def test_empty_comment_refused(self):
        empty = self.env["mail.message"].create(
            {
                "model": "res.partner",
                "res_id": self.partner.id,
                "body": "<p><br></p>",
                "message_type": "comment",
            }
        )
        with self.assertRaises(UserError):
            self._pin(empty)

    # 4
    def test_message_of_other_record_refused(self):
        with self.assertRaises(UserError):
            self._pin(self.other_note)
        self.assertFalse(self.other_note.pinned_at)

    # 5
    def test_channel_refused_and_core_untouched(self):
        channel = self.env["discuss.channel"].create(
            {"name": "pin-test-channel", "channel_type": "channel"}
        )
        channel_message = channel.message_post(
            body="Channel message", message_type="comment"
        )
        with self.assertRaises(UserError):
            channel.message_set_pin(channel_message.id, True)
        before = len(channel.message_ids)
        channel.set_message_pin(channel_message.id, True)
        self.assertTrue(channel_message.pinned_at)
        # core still posts its "pinned a message" notice
        self.assertEqual(len(channel.message_ids), before + 1)

    # 6
    def test_pin_is_silent(self):
        before = self.partner.message_ids
        notif_before = self.env["mail.notification"].search_count([])
        self._pin(self.note)
        self.assertEqual(self.partner.message_ids, before)
        self.assertEqual(self.env["mail.notification"].search_count([]), notif_before)

    # 7
    def test_write_date_unchanged(self):
        self.env.cr.execute(
            "UPDATE mail_message SET write_date = '2020-01-01 00:00:00' WHERE id = %s",
            (self.note.id,),
        )
        self.env.invalidate_all()
        write_date = self.note.write_date
        self._pin(self.note)
        self.env.invalidate_all()
        self.assertEqual(self.note.write_date, write_date)
        self.assertTrue(self.note.pinned_at)

    # 8
    def test_thread_data_includes_old_pinned_messages(self):
        self._pin(self.note)
        for i in range(40):
            self.partner.message_post(
                body="Filler %s" % i, message_type="comment", subtype_xmlid="mail.mt_note"
            )
        partner = self.partner.with_user(self.editor)
        store = Store()
        partner._thread_to_store(store, [], request_list=["pinnedMessages"])
        ids = [m["id"] for m in store.get_result().get("mail.message", [])]
        self.assertEqual(ids, [self.note.id])

    def test_thread_data_without_request_has_no_pins(self):
        self._pin(self.note)
        store = Store()
        self.partner.with_user(self.editor)._thread_to_store(
            store, [], request_list=["display_name"]
        )
        self.assertNotIn("mail.message", store.get_result())
