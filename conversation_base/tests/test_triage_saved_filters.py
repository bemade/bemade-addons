# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria (task #4331): four seeded, shared saved filters --
# Unread, Unanswered, Oldest unanswered first, Mine -- evaluate correctly.

import json
from datetime import timedelta

from odoo import fields
from odoo.tools.safe_eval import safe_eval

from .common_triage import TriageCommon


class TestTriageSavedFilters(TriageCommon):
    def setUp(self):
        super().setUp()
        cls = self
        cls.admin = cls.env.ref("base.user_admin")
        now = fields.Datetime.now()
        Member = cls.env["mail.conversation.member"]
        cls.a = self._inbound()
        cls.b = self._inbound()
        cls.c = self._inbound()
        self._reply(cls.b)
        cls.a.user_id = cls.internal_user
        cls.b.user_id = cls.admin
        for conv, hours in ((cls.a, 1), (cls.c, 3)):
            conv.message_ids.filtered(lambda m: m.external_id).date = now - timedelta(
                hours=hours
            )
        Member.create(
            {"conversation_id": cls.a.id, "user_id": cls.internal_user.id, "unread": True}
        )
        Member.create(
            {"conversation_id": cls.b.id, "user_id": cls.internal_user.id, "unread": False}
        )
        Member.create(
            {"conversation_id": cls.b.id, "user_id": cls.admin.id, "unread": True}
        )
        cls.ids = (cls.a | cls.b | cls.c).ids

    def _run(self, xmlid, user):
        f = self.env.ref("conversation_base.%s" % xmlid)
        domain = safe_eval(f.domain, {"uid": user.id})
        order = ", ".join(json.loads(f.sort)) or None
        return self.Conversation.with_user(user).search(
            domain + [("id", "in", self.ids)], order=order
        )

    def test_unread(self):
        self.assertEqual(self._run("ir_filter_conversation_unread", self.internal_user), self.a)
        self.assertEqual(self._run("ir_filter_conversation_unread", self.admin), self.b)

    def test_unanswered(self):
        self.assertEqual(
            set(self._run("ir_filter_conversation_unanswered", self.admin).ids),
            {self.a.id, self.c.id},
        )

    def test_oldest_unanswered_first(self):
        self.assertEqual(
            self._run("ir_filter_conversation_oldest_unanswered", self.admin).ids,
            [self.c.id, self.a.id],
        )

    def test_mine(self):
        self.assertEqual(self._run("ir_filter_conversation_mine", self.internal_user), self.a)
        self.assertEqual(self._run("ir_filter_conversation_mine", self.admin), self.b)

    def test_filter_records(self):
        for xmlid in (
            "ir_filter_conversation_unread",
            "ir_filter_conversation_unanswered",
            "ir_filter_conversation_oldest_unanswered",
            "ir_filter_conversation_mine",
        ):
            f = self.env.ref("conversation_base.%s" % xmlid)
            self.assertFalse(f.user_ids)
            self.assertFalse(f.is_default)
            self.assertEqual(f.model_id, "mail.conversation")
            self.assertIsInstance(json.loads(f.sort), list)
