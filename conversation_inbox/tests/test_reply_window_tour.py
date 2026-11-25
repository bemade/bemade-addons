# Acceptance criteria: a plain internal user opens the Reply window from a
# shared mailbox's inbox; it comes up prefilled (subject, quoted original)
# with the attachments control in the footer.

from unittest.mock import patch

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

_STUB = {
    "external_id": "rw1",
    "message_id": "<tour-rw1@example.com>",
    "subject": "Reply Window Message",
    "email_from": "tourist@example.com",
    "author": "tourist@example.com",
    "to": ["desk@example.com"],
    "cc": [],
    "date": "2026-08-14 09:00:00",
    "body": "<p>Here is the quote you asked for.</p>",
    "attachments": [],
}


def _fake_browse(self, query=None, page=1):
    return {"items": [_STUB], "page": 1, "page_size": 10, "has_more": False}


@tagged("post_install", "-at_install")
class TestReplyWindowTour(HttpCase):
    def test_reply_window_opens_prefilled_for_internal_user(self):
        user = self.env["res.users"].create(
            {
                "name": "Reply Window Tour User",
                "login": "reply_window_tour_user",
                "password": "reply_window_tour_user",
                "email": "reply_window_tour_user@example.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        self.env["conversation.transport"].create(
            {
                "name": "Reply Window Mailbox",
                "login": "desk@example.com",
                "browsable": True,
                "sendable": True,
                "user_id": False,
            }
        )
        cls = type(self.env["conversation.transport"])
        with patch.object(cls, "_browse", _fake_browse), patch.object(
            cls, "_fetch", lambda self, ext: {"external_id": ext, "rfc822": b""}
        ), patch.object(cls, "_normalize", lambda self, raw: dict(_STUB)):
            self.start_tour(
                "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                "conversation_inbox_reply_window_tour",
                login=user.login,
            )
