# Acceptance criteria (inbox row actions, bulk side):
#   - Ticking rows and running Archive / Delete / Mark read acts on exactly
#     the ticked rows of the page, and on no other.
#   - No bulk action ever opens a message: no body is fetched.
#   - Bulk Delete asks for one confirmation; cancelling calls nothing.
#   - If some items fail, the others still go through, the failed ones stay
#     listed and ticked, and the user sees the server's error and the count.

from unittest.mock import patch

from odoo import api
from odoo.exceptions import UserError
from odoo.tests import HttpCase, tagged
from odoo.tools.misc import mute_logger

_SUBJECTS = {"1": "A", "2": "B", "3": "C", "4": "D"}

# What the tour did to the (fake) mailbox. Module-level because the stubs
# run on the HTTP request threads.
_CALLS = {"archive": [], "trash": [], "mark_read": [], "envelope": []}


def _stub(external_id):
    return {
        "external_id": external_id,
        "message_id": "<bulk-%s@example.com>" % external_id,
        "subject": "Bulk Message %s" % _SUBJECTS[external_id],
        "email_from": "sender%s@example.com" % external_id,
        "author": "sender%s@example.com" % external_id,
        "to": ["desk@example.com"],
        "cc": [],
        "date": "2026-08-14 09:0%s:00" % external_id,
        "body": "<p>Body %s</p>" % external_id,
        "attachments": [],
    }


def _fake_browse(self, query=None, page=1):
    gone = set(_CALLS["archive"]) | {
        ext for ext in _CALLS["trash"] if ext != "4"
    }
    return {
        "items": [_stub(ext) for ext in _SUBJECTS if ext not in gone],
        "page": 1,
        "page_size": 10,
        "has_more": False,
    }


def _fake_archive(self, external_id):
    _CALLS["archive"].append(external_id)
    return True


def _fake_trash(self, external_id):
    _CALLS["trash"].append(external_id)
    if external_id == "4":
        raise UserError(self.env._("Trash refused for message 4."))
    return True


def _fake_mark_read(self, external_id):
    _CALLS["mark_read"].append(external_id)
    return True


@tagged("post_install", "-at_install")
class TestConversationInboxBulkTour(HttpCase):
    def test_bulk_tour(self):
        transport_model = self.env["conversation.transport"]
        transport_model.create(
            {
                "name": "Bulk Mailbox",
                "login": "bulk@example.com",
                "browsable": True,
                "sendable": True,
                "mailbox_writable": True,
                "user_id": False,
            }
        )
        cls = type(transport_model)
        for calls in _CALLS.values():
            calls.clear()
        original_envelope = cls.fetch_envelope

        @api.model
        def _recording_envelope(self, transport_id, external_id):
            _CALLS["envelope"].append(external_id)
            return original_envelope(self, transport_id, external_id)

        with patch.object(cls, "fetch_envelope", _recording_envelope), patch.object(
            cls, "_browse", _fake_browse
        ), patch.object(cls, "_archive_remote", _fake_archive), patch.object(
            cls, "_trash_remote", _fake_trash
        ), patch.object(
            cls, "_mark_read_remote", _fake_mark_read
        ), mute_logger(
            "odoo.http", "odoo.addons.base.models.ir_http"
        ):
            self.start_tour(
                "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                "conversation_inbox_bulk_tour",
                login="admin",
            )
        # Exactly the two ticked rows, and none of the others.
        self.assertEqual(_CALLS["archive"], ["1", "3"])
        # The cancelled confirmation called nothing; the confirmed one tried
        # both remaining rows even though the second one failed.
        self.assertEqual(_CALLS["trash"], ["2", "4"])
        # Mark read ran for the one row still ticked after the failure.
        self.assertEqual(_CALLS["mark_read"], ["4"])
        # Bulk actions never open a message.
        self.assertEqual(_CALLS["envelope"], [])
