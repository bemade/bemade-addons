# Acceptance criteria (collaborative shared drafts, review comments):
#   * A comment on a draft is the draft's own chatter, anchored to that draft
#     and not to the next one.
#   * It never reaches an external party, even when @mentioned, and never
#     makes one a follower.

from .common import DraftCommon


class TestDraftComments(DraftCommon):
    def test_comments_are_anchored_and_internal(self):
        d1 = self._open_draft()
        message = d1.message_post(
            body="Please soften this",
            subtype_xmlid="mail.mt_note",
            partner_ids=[self.partner_p.id, self.user_b.partner_id.id],
        )
        self.assertEqual(message.model, "mail.conversation.draft")
        self.assertEqual(message.res_id, d1.id)

        notifications = self.env["mail.notification"].search(
            [("mail_message_id", "=", message.id)]
        )
        self.assertNotIn(self.partner_p, notifications.res_partner_id)
        self.assertIn(self.user_b.partner_id, notifications.res_partner_id)
        self.assertFalse(
            self.env["mail.mail"].search([("mail_message_id", "=", message.id)])
        )

        d1.message_subscribe([self.partner_p.id])
        self.assertNotIn(self.partner_p, d1.message_partner_ids)

        with self._sending():
            d1.action_send()
        d2 = self._open_draft()
        self.assertNotEqual(d1, d2)
        self.assertNotIn(message, d2.message_ids)
        self.assertIn(message, d1.message_ids)
