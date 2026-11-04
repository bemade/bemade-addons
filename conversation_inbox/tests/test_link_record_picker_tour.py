# Acceptance criteria: a plain internal user links an inbox email to a record
# by searching for it by name in the Link to Record dialog (never typing an
# id), and the conversation created is linked to that very record.

from unittest.mock import patch

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

_STUB = {
    "external_id": "lp1",
    "message_id": "<tour-lp1@example.com>",
    "subject": "Link Picker Message",
    "email_from": "tourist@example.com",
    "author": "tourist@example.com",
    "to": ["desk@example.com"],
    "cc": [],
    "date": "2026-08-14 09:00:00",
    "body": "<p>Hello.</p>",
    "attachments": [],
}


def _fake_browse(self, query=None, page=1):
    return {"items": [_STUB], "page": 1, "page_size": 10, "has_more": False}


@tagged("post_install", "-at_install")
class TestLinkRecordPickerTour(HttpCase):
    def test_link_record_by_name(self):
        user = self.env["res.users"].create(
            {
                "name": "Picker Tour User",
                "login": "picker_tour_user",
                "password": "picker_tour_user",
                "email": "picker_tour_user@example.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        self.env["conversation.transport"].create(
            {
                "name": "Picker Tour Mailbox",
                "browsable": True,
                "user_id": False,
                "record_link_mode": "off",
            }
        )
        partner = self.env["res.partner"].create({"name": "Zed Industries"})
        self.env["res.partner"].create({"name": "Zenith Other"})
        cls = type(self.env["conversation.transport"])
        with patch.object(cls, "_browse", _fake_browse), patch.object(
            cls, "_fetch", lambda self, ext: {"external_id": ext, "rfc822": b""}
        ), patch.object(cls, "_normalize", lambda self, raw: dict(_STUB)):
            self.start_tour(
                "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                "conversation_inbox_link_record_picker_tour",
                login=user.login,
            )
        links = self.env["mail.conversation.link"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", partner.id)]
        )
        self.assertEqual(len(links), 1)
        self.assertEqual(links.conversation_id.name, "Link Picker Message")
