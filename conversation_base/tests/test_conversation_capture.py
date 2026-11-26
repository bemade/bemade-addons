# Acceptance criteria (task #3965):
#   AC-7/AC-8 (test plan #3, load-bearing): quiet-capturing a stub into a
#     NEW conversation creates the conversation, adds From/To/Cc as
#     participants (not followers), posts an mt_note with transport_id
#     falsy + external_id set, maps the correspondent to the From partner
#     (not the acting user), and sends zero external emails.
#   AC-7 (test plan #4): capturing into an EXISTING conversation threads the
#     message and does not duplicate an already-present participant.
#   AC-6 (conversation_inbox's GTD actions rely on these idempotent-capture
#     primitives): _capture_or_find files a not-yet-seen external_id once,
#     and returns the SAME conversation (no duplicate filing) on a repeat
#     call for the same external_id -- so acting twice on one inbox item
#     (e.g. reply, then later reassign) never creates two conversations.

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import TransactionCase, tagged


class TestConversationCapture(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.Participant = cls.env["mail.conversation.participant"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Capture Transport"}
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Customer Corp", "email": "customer@example.com"}
        )

    def _stub(self, **overrides):
        stub = {
            "subject": "Need a quote",
            "body": "<p>Please send a quote.</p>",
            "email_from": "customer@example.com",
            "to": ["sales@example.com"],
            "cc": ["watcher@example.com"],
            "external_id": "ext-msg-1",
        }
        stub.update(overrides)
        return stub

    def _outgoing_mail_ids(self):
        return set(self.env["mail.mail"].search([]).ids)

    def test_capture_into_new_conversation(self):
        before_mail_ids = self._outgoing_mail_ids()

        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="new"
        )

        self.assertTrue(conversation)
        self.assertEqual(conversation.name, "Need a quote")

        # participants, not followers
        self.assertFalse(conversation.message_follower_ids)
        emails = set(conversation.participant_ids.mapped("email_normalized"))
        self.assertEqual(
            emails, {"customer@example.com", "sales@example.com", "watcher@example.com"}
        )

        # correct-correspondent mapping: the From participant resolves to
        # the actual customer partner, not the capturing/admin user.
        requester = conversation.participant_ids.filtered(
            lambda p: p.email_normalized == "customer@example.com"
        )
        self.assertEqual(requester.partner_id, self.customer)
        self.assertEqual(requester.role, "requester")
        self.assertNotEqual(requester.partner_id, self.env.user.partner_id)

        # the posted message is an internal note carrying transport metadata
        messages = conversation.message_ids.filtered(lambda m: m.body)
        self.assertEqual(len(messages), 1)
        message = messages[0]
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        # model contract: transport_id falsy => internal note. Quiet capture
        # deliberately leaves it falsy (the notify-safety guard this relies
        # on, per the task design's Risks section) -- provenance is instead
        # recorded on external_id (message) and primary_transport_id (conv).
        self.assertFalse(message.transport_id)
        self.assertEqual(conversation.primary_transport_id, self.transport)
        self.assertEqual(message.external_id, "ext-msg-1")

        # zero external emails produced
        self.assertEqual(self._outgoing_mail_ids(), before_mail_ids)

    def test_capture_into_existing_conversation_dedups_participants(self):
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="new"
        )
        initial_participant_count = len(conversation.participant_ids)
        initial_message_count = len(conversation.message_ids)
        before_mail_ids = self._outgoing_mail_ids()

        second_stub = self._stub(
            subject="Re: Need a quote",
            body="<p>Following up.</p>",
            external_id="ext-msg-2",
        )
        result = self.Conversation._capture_stub(
            self.transport, second_stub, mode="existing", target=conversation
        )

        self.assertEqual(result, conversation)
        self.assertEqual(
            len(conversation.participant_ids),
            initial_participant_count,
            "no duplicate participants on a follow-up capture",
        )
        self.assertEqual(
            len(conversation.message_ids), initial_message_count + 1
        )
        self.assertEqual(self._outgoing_mail_ids(), before_mail_ids)

    def _captured_message(self, conversation, external_id):
        return conversation.message_ids.filtered(
            lambda m: m.external_id == external_id
        )

    def test_capture_keeps_sent_date_with_offset_new_conversation(self):
        sent = datetime(2025, 11, 4, 9, 15, tzinfo=timezone(timedelta(hours=-5)))
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(date=sent), mode="new"
        )
        message = self._captured_message(conversation, "ext-msg-1")
        self.assertEqual(message.date, datetime(2025, 11, 4, 14, 15))
        self.assertEqual(conversation.last_message_date, datetime(2025, 11, 4, 14, 15))
        self.assertTrue(conversation.unanswered)
        self.assertEqual(conversation.unanswered_since, datetime(2025, 11, 4, 14, 15))

    def test_capture_sent_date_rfc822_string(self):
        conversation = self.Conversation._capture_stub(
            self.transport,
            self._stub(date="Tue, 04 Nov 2025 09:15:00 -0500"),
            mode="new",
        )
        message = self._captured_message(conversation, "ext-msg-1")
        self.assertEqual(message.date, datetime(2025, 11, 4, 14, 15))

    def test_capture_old_mail_into_existing_conversation_sorts_by_date(self):
        conversation = self.Conversation._capture_stub(
            self.transport,
            self._stub(date=datetime(2025, 11, 10, 12, 0, tzinfo=timezone.utc)),
            mode="new",
        )
        self.assertEqual(conversation.last_message_date, datetime(2025, 11, 10, 12, 0))

        self.Conversation._capture_stub(
            self.transport,
            self._stub(
                external_id="ext-msg-old",
                body="<p>Older.</p>",
                date=datetime(
                    2025, 11, 4, 9, 15, tzinfo=timezone(timedelta(hours=-5))
                ),
            ),
            mode="existing",
            target=conversation,
        )
        old = self._captured_message(conversation, "ext-msg-old")
        self.assertEqual(old.date, datetime(2025, 11, 4, 14, 15))
        # the newest message still defines the thread's last activity ...
        self.assertEqual(conversation.last_message_date, datetime(2025, 11, 10, 12, 0))
        # ... and the unanswered stretch starts at the OLDEST inbound mail
        self.assertTrue(conversation.unanswered)
        self.assertEqual(conversation.unanswered_since, datetime(2025, 11, 4, 14, 15))

    def test_capture_without_usable_date_keeps_filing_time(self):
        for index, bad in enumerate((None, False, "", "not a date")):
            external_id = f"ext-bad-{index}"
            before = datetime.now() - timedelta(seconds=5)
            conversation = self.Conversation._capture_stub(
                self.transport,
                self._stub(external_id=external_id, date=bad),
                mode="new",
            )
            message = self._captured_message(conversation, external_id)
            self.assertGreaterEqual(message.date, before)

    def test_capture_link_mode_links_record(self):
        record = self.env["res.partner"].create({"name": "Linked Record"})
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="link", target=record
        )
        self.assertEqual(len(conversation.link_ids), 1)
        link = conversation.link_ids
        self.assertEqual(link.res_model, "res.partner")
        self.assertEqual(link.res_id, record.id)

    def test_capture_or_find_is_idempotent(self):
        transport_model = type(self.transport)
        raw = {"external_id": "ext-idem-1"}
        with patch.object(
            transport_model, "_fetch", return_value=raw, autospec=True
        ), patch.object(
            transport_model,
            "_normalize",
            return_value=self._stub(external_id="ext-idem-1"),
            autospec=True,
        ):
            first = self.Conversation._capture_or_find(self.transport, "ext-idem-1")
            second = self.Conversation._capture_or_find(self.transport, "ext-idem-1")

        self.assertTrue(first)
        self.assertEqual(
            first,
            second,
            "a repeat GTD action on the same inbox item must not file a "
            "second conversation",
        )
        self.assertEqual(
            self.Conversation.search_count(
                [("participant_ids.email", "=", "customer@example.com")]
            ),
            1,
        )

    def test_find_captured_returns_empty_for_unknown_external_id(self):
        self.assertFalse(
            self.Conversation._find_captured(self.transport, "never-seen")
        )

    def test_find_captured_never_crosses_transport(self):
        other_transport = self.env["conversation.transport"].create(
            {"name": "Other Transport"}
        )
        self.Conversation._capture_stub(
            self.transport, self._stub(external_id="ext-cross-1"), mode="new"
        )
        self.assertFalse(
            self.Conversation._find_captured(other_transport, "ext-cross-1")
        )

    def test_all_participant_emails_reply_all_includes_cc(self):
        conversation = self.Conversation._capture_stub(
            self.transport, self._stub(), mode="new"
        )
        reply_only = conversation._all_participant_emails(roles=("to", "requester"))
        reply_all = conversation._all_participant_emails()
        self.assertNotIn("watcher@example.com", reply_only)
        self.assertIn("watcher@example.com", reply_all)
        self.assertIn("customer@example.com", reply_all)


@tagged("post_install", "-at_install")
class TestCaptureSkipsAliasParticipants(MailCommon):
    # Acceptance criteria:
    #   - a captured reply-all whose To or Cc holds an Odoo alias adds no
    #     participant for that alias; the other addresses are added as before;
    #   - the next reply draft does not list the alias;
    #   - the gateway path is unchanged (covered by test_conversation_gateway).

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Alias Capture Transport"}
        )
        cls.alias = cls.env["mail.alias"].create(
            {
                "alias_name": "team-inbox",
                "alias_model_id": cls.env["ir.model"]._get("mail.conversation").id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (cls.alias.alias_name, cls.mail_alias_domain.name)

    def _capture(self, **overrides):
        stub = {
            "subject": "Reply all",
            "body": "<p>Hello</p>",
            "email_from": "customer@example.com",
            "to": ["Sales <sales@example.com>"],
            "cc": ["watcher@example.com"],
            "external_id": "alias-ext-1",
        }
        stub.update(overrides)
        return self.Conversation._capture_stub(self.transport, stub, mode="new")

    def _emails(self, conversation):
        return set(conversation.participant_ids.mapped("email_normalized"))

    def test_alias_in_to_is_not_a_participant(self):
        conversation = self._capture(
            to=["sales@example.com", "Team <%s>" % self.alias_email]
        )
        self.assertEqual(
            self._emails(conversation),
            {"customer@example.com", "sales@example.com", "watcher@example.com"},
        )

    def test_alias_in_cc_is_not_a_participant(self):
        conversation = self._capture(cc=[self.alias_email.upper(), "w@example.com"])
        self.assertEqual(
            self._emails(conversation),
            {"customer@example.com", "sales@example.com", "w@example.com"},
        )

    def test_alias_only_recipients_leave_just_the_sender(self):
        conversation = self._capture(to=[self.alias_email], cc=[])
        self.assertEqual(self._emails(conversation), {"customer@example.com"})

    def _local_part_alias(self, name):
        """An alias that core also matches on its local part alone
        (``alias_incoming_local``), with no ``mail.catchall.domain.allowed``:
        then ``_find_aliases`` matches ``<name>@<any domain>``."""
        self.env["ir.config_parameter"].sudo().set_param(
            "mail.catchall.domain.allowed", False
        )
        return self.env["mail.alias"].create(
            {
                "alias_name": name,
                "alias_model_id": self.env["ir.model"]._get("mail.conversation").id,
                "alias_domain_id": self.mail_alias_domain.id,
                "alias_incoming_local": True,
            }
        )

    def test_local_part_alias_keeps_outside_address(self):
        alias = self._local_part_alias("orders")
        outside = "orders@customer.example.com"
        self.assertIn(
            outside,
            self.env["mail.alias.domain"]._find_aliases([outside]),
            "core matches the outside address on the local part alone",
        )
        conversation = self._capture(
            to=["Orders <%s>" % outside, "sales@example.com"],
            cc=[alias.alias_full_name, "watcher@example.com"],
        )
        self.assertEqual(
            self._emails(conversation),
            {
                "customer@example.com",
                outside,
                "sales@example.com",
                "watcher@example.com",
            },
        )

    def test_local_part_alias_on_other_alias_domain_is_left_out(self):
        self._local_part_alias("orders")
        other_domain = self.env["mail.alias.domain"].create(
            {"name": "other-alias.example.com"}
        )
        own_address = "orders@%s" % other_domain.name
        conversation = self._capture(to=[own_address, "sales@example.com"])
        self.assertEqual(
            self._emails(conversation),
            {"customer@example.com", "sales@example.com", "watcher@example.com"},
        )

    def test_alias_domain_catchall_and_bounce_are_left_out(self):
        conversation = self._capture(
            cc=[
                self.mail_alias_domain.catchall_email,
                self.mail_alias_domain.bounce_email,
                "watcher@example.com",
            ]
        )
        self.assertEqual(
            self._emails(conversation),
            {"customer@example.com", "sales@example.com", "watcher@example.com"},
        )
