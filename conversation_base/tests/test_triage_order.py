# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
#
# Acceptance criteria (task #4331): the default order is newest activity
# first (``last_message_date desc, id desc``).

from odoo import fields
from datetime import timedelta

from .common_triage import TriageCommon


class TestTriageOrder(TriageCommon):
    def test_default_order(self):
        # no "Conversation created" log note: it would count as activity
        Conversation = self.Conversation.with_context(mail_create_nolog=True)
        c1 = Conversation.create({"name": "c1"})
        c2 = Conversation.create({"name": "c2"})
        c3 = Conversation.create({"name": "c3"})
        self._inbound(c1)
        self._inbound(c2)
        now = fields.Datetime.now()
        for conv, hours in ((c1, 0), (c2, 5)):
            conv.message_ids.filtered(lambda m: m.external_id).date = now - timedelta(
                hours=hours + 1
            )
        # c3 has no messages: its create_date is the newest, but older than c1.
        self.env.cr.execute(
            "UPDATE mail_conversation SET create_date=%s WHERE id=%s",
            (now - timedelta(hours=3), c3.id),
        )
        c3.invalidate_recordset(["create_date"])
        c3.last_message_date = now - timedelta(hours=3)
        ids = [c1.id, c2.id, c3.id]
        self.assertEqual(
            self.Conversation.search([("id", "in", ids)]).ids, [c1.id, c3.id, c2.id]
        )

    def test_tie_breaks_by_id_desc(self):
        a = self.Conversation.create({"name": "a"})
        b = self.Conversation.create({"name": "b"})
        stamp = fields.Datetime.now()
        (a | b).write({"last_message_date": stamp})
        self.assertEqual(
            self.Conversation.search([("id", "in", (a | b).ids)]).ids, [b.id, a.id]
        )
