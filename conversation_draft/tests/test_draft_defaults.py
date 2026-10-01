# Acceptance criteria (collaborative shared drafts, defaults):
#   * The default transport is the one the correspondent last wrote on, else
#     the conversation's primary one, and only if the current user may send
#     from it; otherwise it is left empty.
#   * Default recipients come from the external participants (requester/to
#     as To, cc as Cc, internal people left out), keep an address-less
#     participant visible but unreachable, and never create a res.partner.
#   * With conversation_participant_scope installed, a one-off Cc is
#     pre-filled for the next outbound message only.

from odoo.tests import tagged

from .common import DraftCommon


class TestDraftDefaults(DraftCommon):
    def _inbound(self, transport, author=None):
        message = self.conversation.message_post(
            body="<p>question</p>",
            author_id=(author or self.partner_p).id,
            subtype_xmlid="mail.mt_comment",
        )
        message.write({"transport_id": transport.id})
        return message

    def _fresh_draft(self):
        self.Draft.search(
            [("conversation_id", "=", self.conversation.id)]
        ).action_discard()
        return self._open_draft()

    def test_transport_follows_the_correspondent(self):
        self._inbound(self.t2)
        self.assertEqual(self._open_draft().transport_id, self.t2)

    def test_internal_authored_messages_do_not_pick_the_transport(self):
        self._inbound(self.t2, author=self.user_b.partner_id)
        self.assertEqual(self._open_draft().transport_id, self.t1)

    def test_non_sendable_candidate_falls_back_to_primary(self):
        self._inbound(self.t2)
        self.t2.sendable = False
        self.assertEqual(self._open_draft().transport_id, self.t1)

    def test_unreadable_transport_leaves_the_field_empty(self):
        self.t1.user_id = self.user_b
        self.assertFalse(self._open_draft(self.user_a).transport_id)

    def test_default_recipients(self):
        partners_before = self.env["res.partner"].search_count([])
        draft = self._open_draft()
        by_email = {r.email: r for r in draft.recipient_ids if r.email}
        self.assertEqual(by_email["cust@example.com"].mode, "to")
        self.assertEqual(by_email["p@example.com"].mode, "to")
        self.assertEqual(by_email["cc@example.com"].mode, "cc")
        self.assertNotIn("internal@example.com", by_email)
        unreachable = draft.recipient_ids.filtered(lambda r: not r.is_reachable)
        self.assertEqual(unreachable.partner_id, self.partner_noemail)
        self.assertTrue(draft.has_unreachable_recipients)
        self.assertEqual(partners_before, self.env["res.partner"].search_count([]))


@tagged("post_install", "-at_install")
class TestDraftDefaultsScope(DraftCommon):
    """Needs conversation_participant_scope fully loaded, hence post-install."""

    def test_cc_once_is_prefilled_for_the_next_message_only(self):
        if "receives_updates" not in self.env["mail.conversation.participant"]._fields:
            self.skipTest("conversation_participant_scope is not installed")
        # an earlier outbound message, older than anything added below
        previous = self.conversation.message_post(
            body="<p>earlier</p>",
            author_id=self.user_a.partner_id.id,
            subtype_xmlid="mail.mt_comment",
        )
        previous.write({"transport_id": self.t1.id})
        self.env.cr.execute(
            "UPDATE mail_message SET create_date = create_date - interval '1 hour' "
            "WHERE id = %s",
            [previous.id],
        )
        self.env.invalidate_all()
        self.conversation._add_cc_once(emails=["once@example.com"])
        first = self._open_draft()
        modes = {r.email: r.mode for r in first.recipient_ids}
        self.assertEqual(modes.get("once@example.com"), "cc")
        # ordinary participants keep being prefilled
        self.assertEqual(modes.get("cust@example.com"), "to")

        with self._sending():
            first.action_send()
        second = self._open_draft()
        modes = {r.email: r.mode for r in second.recipient_ids}
        self.assertNotIn("once@example.com", modes)
        self.assertEqual(modes.get("cust@example.com"), "to")
