# Acceptance criteria (collaborative shared drafts, access):
#   * Access to a draft, its recipients and its live-editing bus channel
#     follows access to the conversation it belongs to -- not who created it.

from unittest.mock import MagicMock, patch

from odoo import Command
from odoo.exceptions import AccessError

from .common import DraftCommon


class TestDraftAccess(DraftCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env["res.groups"].create({"name": "Draft Restricted"})
        cls.user_c = cls._make_user("draft_user_c")
        cls.user_c.group_ids = [Command.link(cls.group.id)]
        cls.env["ir.rule"].create(
            {
                "name": "Conversations: assignee only (test)",
                "model_id": cls.env["ir.model"]._get_id("mail.conversation"),
                "groups": [Command.link(cls.group.id)],
                "domain_force": "[('user_id', '=', user.id)]",
            }
        )
        cls.conversation.user_id = cls.user_a

    def test_access_follows_the_conversation(self):
        draft = self._open_draft(self.user_a)
        as_c = draft.with_user(self.user_c)
        self.assertNotIn(draft, self.Draft.with_user(self.user_c).search([]))
        self.assertIn(draft, self.Draft.with_user(self.user_a).search([]))
        with self.assertRaises(AccessError):
            as_c.check_access("read")
        with self.assertRaises(AccessError):
            as_c.check_access("write")
        recipients = self.env["mail.conversation.draft.recipient"]
        self.assertTrue(draft.recipient_ids)
        self.assertFalse(recipients.with_user(self.user_c).search([]))
        with self.assertRaises(AccessError):
            draft.recipient_ids.with_user(self.user_c).check_access("read")

    def test_collaboration_bus_channel_is_gated(self):
        draft = self._open_draft(self.user_a)
        name = f"editor_collaboration:mail.conversation.draft:body:{draft.id}"
        channel = (
            self.env.registry.db_name,
            "editor_collaboration",
            "mail.conversation.draft",
            "body",
            draft.id,
        )
        websocket = self.env["ir.websocket"]
        with patch("odoo.addons.bus.models.ir_websocket.wsrequest", new=MagicMock()):
            as_c = websocket.with_user(self.user_c)._build_bus_channel_list([name])
            as_a = websocket.with_user(self.user_a)._build_bus_channel_list([name])
        # other channels in the list are records, which warn when compared
        self.assertNotIn(channel, [c for c in as_c if isinstance(c, tuple)])
        self.assertIn(channel, [c for c in as_a if isinstance(c, tuple)])
