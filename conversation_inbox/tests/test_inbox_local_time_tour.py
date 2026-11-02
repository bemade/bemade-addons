# Acceptance criteria: the Inbox screen shows a message's date in the
# viewer's time zone (here a Toronto browser), in Odoo's date-time format.
# A message received at 09:00 UTC in August shows 05:00.

from unittest.mock import patch

from odoo.tests import HttpCase, tagged


def _stub(external_id, subject, date):
    return {
        "external_id": external_id,
        "message_id": "<local-time-%s@example.com>" % external_id,
        "subject": subject,
        "email_from": "sender@example.com",
        "author": "sender@example.com",
        "to": ["desk@example.com"],
        "cc": [],
        "date": date,
        "body": "<p>Hello.</p>",
        "attachments": [],
    }


def _fake_browse(self, query=None, page=1):
    if (page or 1) <= 1:
        items = [_stub("lt1", "Local Time Message", "2026-08-14 09:00:00")]
        return {"items": items, "page": 1, "page_size": 1, "has_more": True}
    items = [_stub("lt2", "Second Page Message", "2026-01-15 17:00:00")]
    return {"items": items, "page": 2, "page_size": 1, "has_more": False}


@tagged("post_install", "-at_install")
class TestInboxLocalTimeTour(HttpCase):
    def test_inbox_shows_dates_in_the_viewers_zone(self):
        self.env["conversation.transport"].create(
            {
                "name": "Local Time Mailbox",
                "login": "desk@example.com",
                "browsable": True,
                "user_id": False,
            }
        )
        cls = type(self.env["conversation.transport"])
        with patch.object(cls, "_browse", _fake_browse):
            self.start_tour(
                "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                "conversation_inbox_local_time_tour",
                login="admin",
            )
