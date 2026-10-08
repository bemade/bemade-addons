# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria (task #4331): a cron resurfaces lapsed snoozes by
# clearing ``snooze_until`` and ``is_handled`` on the member row only; it
# never touches ``unread`` or the conversation ``state`` and is idempotent.

from datetime import timedelta

from odoo import fields

from .common_triage import TriageCommon


class TestSnoozeCron(TriageCommon):
    def _member(self, user, **vals):
        return self.env["mail.conversation.member"].create(
            dict(vals, conversation_id=self.conv.id, user_id=user.id)
        )

    def _run_cron(self):
        # The cron's own cursor cannot see this test's uncommitted rows, so run
        # exactly what the cron's code runs, on the test environment.
        self.env["mail.conversation.member"]._cron_resurface_snoozed()

    def setUp(self):
        super().setUp()
        self.conv = self.Conversation.create({"name": "snz", "state": "snoozed"})

    def test_lapsed_snooze_resurfaces(self):
        now = fields.Datetime.now()
        m_me = self._member(
            self.internal_user,
            is_handled=True,
            snooze_until=now - timedelta(minutes=1),
            unread=False,
        )
        m_other = self._member(
            self.env.ref("base.user_admin"), is_handled=True, unread=True
        )
        self._run_cron()
        self.assertFalse(m_me.snooze_until)
        self.assertFalse(m_me.is_handled)
        self.assertFalse(m_me.unread)
        self.assertTrue(m_other.is_handled)
        self.assertTrue(m_other.unread)
        self.assertFalse(m_other.snooze_until)
        self.assertEqual(self.conv.state, "snoozed")

    def test_future_snooze_untouched(self):
        until = fields.Datetime.now() + timedelta(hours=1)
        member = self._member(self.internal_user, is_handled=True, snooze_until=until)
        self._run_cron()
        self.assertTrue(member.is_handled)
        self.assertEqual(member.snooze_until, until)

    def test_idempotent(self):
        member = self._member(
            self.internal_user,
            is_handled=True,
            snooze_until=fields.Datetime.now() - timedelta(minutes=1),
        )
        self._run_cron()
        snapshot = member.read(["snooze_until", "is_handled", "unread", "write_date"])
        self._run_cron()
        member.invalidate_recordset()
        self.assertEqual(
            member.read(["snooze_until", "is_handled", "unread", "write_date"]),
            snapshot,
        )

    def test_cron_record(self):
        cron = self.env.ref("conversation_base.ir_cron_conversation_resurface_snoozed")
        self.assertTrue(cron.active)
        self.assertEqual(cron.model_name, "mail.conversation.member")
        self.assertEqual(cron.code.strip(), "model._cron_resurface_snoozed()")
        minutes = cron.interval_number * {
            "minutes": 1,
            "hours": 60,
            "days": 1440,
            "weeks": 10080,
            "months": 43200,
        }[cron.interval_type]
        self.assertLessEqual(minutes, 15)
