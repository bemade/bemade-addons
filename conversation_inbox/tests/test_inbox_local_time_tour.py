# Acceptance criteria: the Inbox screen shows a message's date in the
# viewer's time zone (here a Toronto browser), in Odoo's date-time format.
# A message sent at 18:10 Toronto time (23:10 UTC) shows 18:10.

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
        items = [_stub("lt1", "Local Time Message", "2026-11-01 23:10:20")]
        return {"items": items, "page": 1, "page_size": 1, "has_more": True}
    items = [_stub("lt2", "Second Page Message", "2026-01-15 17:00:00")]
    return {"items": items, "page": 2, "page_size": 1, "has_more": False}


@tagged("post_install", "-at_install")
class TestInboxLocalTimeTour(HttpCase):
    def test_inbox_shows_dates_in_the_viewers_zone(self):
        # The flow reads the time as "18:10", which is how a 24-hour
        # language (fr_CA, the demo's screen language) shows it. Pin the
        # admin's language to a 24-hour time format so the assertion does
        # not depend on which language the test database runs in (en_US
        # shows "06:10:20 PM").
        admin = self.env.ref("base.user_admin")
        self.env["res.lang"]._lang_get(admin.lang).time_format = "%H:%M:%S"
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
