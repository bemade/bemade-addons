# Acceptance criteria (AC7/AC8/AC9):
#   13. quiet_email_ingest is seeded from the team default (and stays
#       overridable per conversation);
#   14. quiet ON: an email-originated post is recorded but raises no
#       notification, no inbox bus event and no web push (AC9 pop-up smoke);
#   15. control, quiet OFF (default): the same email notifies in-app;
#   16. quiet only affects email-originated posts, not internal comments;
#   17. moving to Done (or archiving) marks every partner's unread inbox
#       notifications on the conversation's own messages as read, over the
#       bus, and leaves other conversations untouched.

from odoo.tests import tagged

from .common import ConversationNotifyCommon


@tagged("post_install", "-at_install")
class TestConversationQuietIngest(ConversationNotifyCommon):
    def _threaded_inbound(self, conversation, n):
        first = conversation.message_ids.sorted("id")[-1]
        return self._inbound(
            "<quiet-%s@example.com>" % n, in_reply_to=first.message_id
        )

    def _start_conversation(self, quiet):
        conv_id = self._inbound("<quiet-0-%s@example.com>" % quiet)
        conversation = self.env["mail.conversation"].browse(conv_id)
        conversation.quiet_email_ingest = quiet
        self._follow_all(conversation, self.assignee.partner_id)
        self.env.flush_all()
        return conversation

    def test_13_quiet_seeding(self):
        team = self.env["mail.conversation.team"].create(
            {"name": "Quiet Team", "quiet_email_ingest": True}
        )
        self.alias.alias_defaults = "{'team_id': %d}" % team.id
        conv = self.env["mail.conversation"].browse(self._inbound("<seed-1@example.com>"))
        self.assertEqual(conv.team_id, team)
        self.assertTrue(conv.quiet_email_ingest)
        self.assertFalse(self.conversation.quiet_email_ingest)
        conv.quiet_email_ingest = False
        conv.flush_recordset()
        conv.invalidate_recordset()
        self.assertFalse(conv.quiet_email_ingest)

    def test_14_quiet_suppresses_in_app_for_email(self):
        conversation = self._start_conversation(quiet=True)
        self._setup_push_devices_for_partners(self.assignee.partner_id)
        with self.mock_push_to_end_point(), self.mock_bus():
            self._threaded_inbound(conversation, 1)
            self.env.flush_all()
        message = conversation.message_ids.sorted("id")[-1]
        self.assertEqual(message.message_type, "email")
        self.assertTrue(message.body)
        self.assertFalse(self._notifs(message))
        self.assertFalse(
            [
                n
                for n in self._new_bus_notifs
                if "mail.message/inbox" in n.message
            ]
        )
        self.assertNoPushNotification()

    def test_15_control_not_quiet(self):
        conversation = self._start_conversation(quiet=False)
        self._setup_push_devices_for_partners(self.assignee.partner_id)
        with self.mock_push_to_end_point(), self.mock_bus():
            self._threaded_inbound(conversation, 2)
            self.env.flush_all()
        message = conversation.message_ids.sorted("id")[-1]
        self.assertEqual(message.message_type, "email")
        self.assertEqual(
            self._notifs(message, self.assignee.partner_id).notification_type, "inbox"
        )
        self.assertTrue(
            [
                n
                for n in self._new_bus_notifs
                if "mail.message/inbox" in n.message
            ]
        )
        self.push_to_end_point_mocked.assert_called()

    def test_16_quiet_only_affects_email(self):
        conversation = self._start_conversation(quiet=True)
        message = conversation.with_user(self.other_internal).message_post(
            body="ping",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=self.assignee.partner_id.ids,
        )
        self.env.flush_all()
        self.assertEqual(
            self._notifs(message, self.assignee.partner_id).notification_type, "inbox"
        )


@tagged("post_install", "-at_install")
class TestConversationDoneClearsNeedaction(ConversationNotifyCommon):
    def _notify_two(self, conversation, n=1):
        messages = self.env["mail.message"]
        for i in range(n):
            messages |= conversation.with_user(self.user_employee).message_post(
                body="n%s" % i,
                subtype_xmlid="mail.mt_note",
                partner_ids=(self.assignee | self.other_internal).partner_id.ids,
            )
        return messages

    def _unread(self, messages):
        return self.env["mail.notification"].sudo().search(
            [("mail_message_id", "in", messages.ids), ("is_read", "=", False)]
        )

    def test_17_done_clears_needaction(self):
        conv_b = self.env["mail.conversation"].create({"name": "B"})
        messages_a = self._notify_two(self.conversation, n=2)
        messages_b = self._notify_two(conv_b)
        self.env.flush_all()
        self.assertEqual(len(self._unread(messages_a)), 4)
        with self.mock_bus():
            self.conversation.write({"state": "done"})
            self.env.flush_all()
        self.assertFalse(self._unread(messages_a))
        self.assertEqual(len(self._unread(messages_b)), 2)
        self.assertEqual(
            len(
                [
                    n
                    for n in self._new_bus_notifs
                    if "mail.message/mark_as_read" in n.message
                ]
            ),
            2,
        )
        # already done: no-op
        with self.mock_bus():
            self.conversation.write({"state": "done"})
            self.env.flush_all()
        self.assertFalse(self._new_bus_notifs)

    def test_17b_archive_clears_needaction(self):
        conv = self.env["mail.conversation"].create({"name": "C"})
        messages = self._notify_two(conv)
        self.env.flush_all()
        self.assertTrue(self._unread(messages))
        conv.action_archive()
        self.env.flush_all()
        self.assertFalse(self._unread(messages))
