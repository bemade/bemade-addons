# Acceptance criteria (task #3966, slice 04a -- backend):
#   AC1: ``unanswered`` is True when the latest message that counts
#     (notifications and internal users' notes ignored) is from a
#     non-internal party -- an external partner, a bare email_from, or a
#     captured stub. A conversation without such a message is not unanswered.
#   AC2: ``unassigned`` tracks ``user_id``; ``last_activity`` is the date of
#     the latest non-notification message (creation date when none).
#   AC3: an inbound (non-internal) post reopens a ``waiting`` conversation;
#     internal posts do not; ``done`` is durable.
#   AC4: the snooze cron resurfaces per-user and team-level snoozes,
#     idempotently, and never touches ``is_handled``.
#   AC5: a non-notification post marks every other member's row unread;
#     opening a conversation marks it read for the opener only.
#   AC6/AC7: seeded filters evaluate without error.

import json
from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import TriageCommon


@tagged("post_install", "-at_install")
class TestConversationTriageFacets(TriageCommon):
    # -- unanswered / last_activity / last_message_id ----------------------

    def test_unanswered_inbound_comment_from_external_partner(self):
        conv = self._conversation()
        message = self._post(conv, self.ext_partner)
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.last_message_id, message)
        self.assertEqual(conv.last_activity, message.date)

    def test_unanswered_cleared_by_internal_reply(self):
        conv = self._conversation()
        self._post(conv, self.ext_partner)
        self._post(conv, self.user_a)
        self.assertFalse(conv.unanswered)

    def test_internal_note_does_not_answer(self):
        conv = self._conversation()
        self._post(conv, self.ext_partner)
        note = self._post(conv, self.user_a, note=True)
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.last_message_id, note)

    def test_unanswered_bare_email_and_captured_stub(self):
        transport = self.env["conversation.transport"].create({"name": "T"})
        stub = {
            "subject": "Hello",
            "body": "<p>Hi</p>",
            "email_from": "nobody@unknown-example.org",
            "to": [],
            "cc": [],
            "external_id": "triage-stub-1",
        }
        conv = self.Conversation._capture_stub(transport, stub)
        self.assertTrue(conv.unanswered)
        conv2 = self.Conversation._capture_stub(
            transport,
            dict(stub, external_id="triage-stub-2", author_id=self.ext_partner.id),
        )
        self.assertTrue(conv2.unanswered)

    def test_notification_ignored_and_empty_conversation(self):
        conv = self._conversation()
        self.assertFalse(conv.unanswered)
        self.assertEqual(conv.last_activity, conv.create_date)
        self.assertFalse(conv.last_message_id)
        message = self._post(conv, self.ext_partner)
        conv._message_log(body="<p>tracking</p>")
        conv._trigger_message_facets()
        self.assertTrue(conv.unanswered)
        self.assertEqual(conv.last_message_id, message)

    def test_auto_comment_is_not_an_answer(self):
        conv = self._conversation()
        self._post(conv, self.ext_partner)
        conv.message_post(
            body="<p>We received your request</p>",
            message_type="auto_comment",
            subtype_xmlid="mail.mt_comment",
            author_id=self.env.ref("base.partner_root").id,
        )
        self.assertTrue(conv.unanswered)

    def test_outbound_reply_answers(self):
        transport = self.env["conversation.transport"].create(
            {"name": "Out", "sendable": True}
        )
        conv = self._conversation(primary_transport_id=transport.id)
        self._post(conv, self.ext_partner)
        self.assertTrue(conv.unanswered)
        with patch.object(type(transport), "_send", return_value="out-1"):
            conv.with_user(self.user_a).action_reply("<p>On it</p>")
        self.assertFalse(conv.unanswered)

    # -- unassigned ---------------------------------------------------------

    def test_unassigned_tracks_user_id(self):
        conv = self._conversation()
        self.assertTrue(conv.unassigned)
        self.assertIn(
            conv, self.Conversation.search([("unassigned", "=", True)])
        )
        conv.user_id = self.user_a
        self.assertFalse(conv.unassigned)
        conv.user_id = False
        self.assertTrue(conv.unassigned)

    # -- lifecycle -----------------------------------------------------------

    def test_waiting_reopens_on_gateway_reply(self):
        conv = self._conversation(state="waiting")
        out = conv.message_post(
            body="<p>Question for you</p>",
            subtype_xmlid="mail.mt_comment",
            message_id="<triage-out-1@example.com>",
        )
        self.assertEqual(out.message_id, "<triage-out-1@example.com>")
        mime = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: <triage-in-1@example.com>\n"
            "In-Reply-To: <triage-out-1@example.com>\n"
            "References: <triage-out-1@example.com>\n"
            "Subject: Re: Question\n"
            "From: External Customer <customer@ext-example.com>\n"
            "To: nobody@test.mycompany.com\n"
            'Content-Type: text/plain; charset="UTF-8"\n'
            "\n"
            "Here is my answer.\n"
        )
        self.env["mail.thread"].sudo().message_process(False, mime)
        self.assertEqual(conv.state, "open")

    def test_waiting_not_reopened_by_internal_post(self):
        conv = self._conversation(state="waiting")
        self._post(conv, self.user_a, note=True)
        self.assertEqual(conv.state, "waiting")
        self._post(conv, self.user_a)
        self.assertEqual(conv.state, "waiting")

    def test_done_is_durable_on_inbound_reply(self):
        conv = self._conversation(state="done")
        row = self._member(conv, self.user_a, unread=False, is_handled=True)
        self._post(conv, self.ext_partner)
        self.assertEqual(conv.state, "done")
        self.assertTrue(row.unread)
        self.assertTrue(row.is_handled)

    def test_unread_fanout_excludes_author_and_actor(self):
        conv = self._conversation()
        row_a = self._member(conv, self.user_a, unread=False)
        row_b = self._member(conv, self.user_b, unread=False)
        self._post(conv, self.user_b)
        self.assertTrue(row_a.unread)
        self.assertFalse(row_b.unread)

    def test_open_marks_read_creates_row(self):
        conv = self._conversation()
        as_b = conv.with_user(self.user_b)
        # reading never marks read
        as_b.web_read({"name": {}})
        self.assertFalse(self.Member.search([("conversation_id", "=", conv.id)]))
        as_b.action_mark_read()
        row = self.Member.search([("conversation_id", "=", conv.id)])
        self.assertEqual(row.user_id, self.user_b)
        self.assertFalse(row.unread)
        # an already-unread row is cleared, other users' rows are not
        row_a = self._member(conv, self.user_a, unread=True)
        row.unread = True
        as_b.action_mark_read()
        self.assertFalse(row.unread)
        self.assertTrue(row_a.unread)

    def test_mark_read_dispatches_read_write(self):
        """Mirror web's DataSet._call_kw_readonly MRO walk: action_mark_read
        must not resolve to a read-only dispatch (it writes the member row),
        and web_read/web_search_read must stay side-effect free."""
        model_class = type(self.env["mail.conversation"])
        for cls in model_class.mro():
            method = getattr(cls, "action_mark_read", None)
            if method is not None and hasattr(method, "_readonly"):
                self.fail("action_mark_read must not declare _readonly")
        resolved = None
        for cls in model_class.mro():
            method = getattr(cls, "web_read", None)
            if method is not None and hasattr(method, "_readonly"):
                resolved = method._readonly
                break
        self.assertTrue(resolved, "web_read must stay a pure read")

    # -- cron ----------------------------------------------------------------

    def test_cron_per_user_snooze_resurfaces(self):
        now = fields.Datetime.now()
        conv = self._conversation()
        row = self._member(
            conv,
            self.user_a,
            unread=False,
            is_handled=False,
            snooze_until=now + timedelta(hours=1),
        )
        handled = self._member(
            conv,
            self.user_b,
            unread=False,
            is_handled=True,
            snooze_until=now - timedelta(hours=1),
        )
        with freeze_time(now):
            self.Conversation._cron_resurface_snoozed()
        self.assertTrue(row.snooze_until)
        self.assertFalse(row.unread)
        with freeze_time(now + timedelta(hours=2)):
            self.Conversation._cron_resurface_snoozed()
            self.assertFalse(row.snooze_until)
            self.assertTrue(row.unread)
            row.unread = False
            self.Conversation._cron_resurface_snoozed()  # idempotent
            self.assertFalse(row.unread)
        self.assertTrue(handled.is_handled)
        self.assertFalse(handled.snooze_until)
        self.assertFalse(row.is_handled)

    def test_cron_team_snooze_resurfaces(self):
        now = fields.Datetime.now()
        conv = self._conversation(
            state="snoozed", team_snooze_until=now + timedelta(hours=1)
        )
        forever = self._conversation(state="snoozed")
        rows = self._member(conv, self.user_a, unread=False) | self._member(
            conv, self.user_b, unread=False
        )
        with freeze_time(now + timedelta(hours=2)):
            self.Conversation._cron_resurface_snoozed()
        self.assertEqual(conv.state, "open")
        self.assertFalse(conv.team_snooze_until)
        self.assertTrue(all(rows.mapped("unread")))
        self.assertEqual(forever.state, "snoozed")

    def test_leaving_snoozed_clears_team_snooze(self):
        conv = self._conversation(
            state="snoozed",
            team_snooze_until=fields.Datetime.now() + timedelta(days=1),
        )
        conv.state = "done"
        self.assertFalse(conv.team_snooze_until)

    # -- seeding ---------------------------------------------------------------

    def test_assignment_seeds_members(self):
        team = self.env["mail.conversation.team"].create(
            {
                "name": "Triage team",
                "member_ids": [Command.set((self.user_a | self.user_b).ids)],
            }
        )
        conv = self._conversation()
        existing = self._member(conv, self.user_a, unread=True)
        conv.with_user(self.user_a).write({"team_id": team.id})
        rows = self.Member.search([("conversation_id", "=", conv.id)])
        self.assertEqual(rows.user_id, self.user_a | self.user_b)
        self.assertTrue(rows.filtered(lambda r: r.user_id == self.user_b).unread)
        # untouched: user_a's pre-existing row keeps its value
        self.assertTrue(existing.unread)
        fresh = self._conversation()
        fresh.with_user(self.user_a).write({"user_id": self.user_a.id})
        row = self.Member.search([("conversation_id", "=", fresh.id)])
        self.assertFalse(row.unread)

    # -- seeded filters ---------------------------------------------------------

    def test_seeded_filters_evaluate(self):
        filters = self.env["ir.filters"].search(
            [
                ("model_id", "=", "mail.conversation"),
                ("action_id", "=", self.env.ref("conversation_base.mail_conversation_action").id),
            ]
        )
        self.assertGreaterEqual(len(filters), 5)
        Conversation = self.env["mail.conversation"].with_user(self.user_a)
        for flt in filters:
            self.assertFalse(flt.user_ids, flt.name)
            domain = safe_eval(flt.domain, {"uid": self.user_a.id})
            Conversation.search_count(domain)
            for item in json.loads(flt.sort):
                self.assertIn(item.split()[0], Conversation._fields, flt.name)
