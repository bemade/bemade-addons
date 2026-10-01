# Acceptance criteria (task #3965, AC5/AC6 -- the viewer itself):
#   - The inbox client action mounts, lists a browse page, pages
#     forward/back, expands an item, and opens each triage dialog.
#   - Mark read / Archive / Delete (cancel + confirm) / Hide
#     reach the right server call -- or none, for a cancel and for Hide --
#     and the row leaves or stays as appropriate.
#   - The composer opens prefilled (subject, recipient, quoted original)
#     with the attachments control reachable without scrolling past the
#     draft.
#
# Why this exists as a TOUR and not more TransactionCase tests: the two
# defects that shipped this feature broken were both invisible to Python.
# The triage buttons were dead because an inline doAction dict used
# `view_mode` where the client action schema wants `views` -- server-side
# nothing is wrong, the wizards work when called directly, and every
# wizard test passed. Only a browser clicking the real button sees it.

from unittest.mock import patch

from odoo.tests import HttpCase, tagged

_TOUR_ITEMS = {
    "1": {
        "subject": "Tour Message A",
        "email_from": "tourist@example.com",
        "date": "2026-08-14 09:00:00",
    },
    "2": {
        "subject": "Tour Message B",
        "email_from": "other@example.com",
        "date": "2026-08-14 08:00:00",
    },
    "3": {
        "subject": "Tour Message C",
        "email_from": "third@example.com",
        "date": "2026-08-13 17:00:00",
    },
}


def _stub(external_id):
    """One canonical `_normalize` dict, as the engine would return it."""
    item = _TOUR_ITEMS[external_id]
    return {
        "external_id": external_id,
        "message_id": "<tour-%s@example.com>" % external_id,
        "subject": item["subject"],
        "email_from": item["email_from"],
        "author": item["email_from"],
        "to": ["desk@example.com"],
        "cc": ["watcher@example.com"],
        "date": item["date"],
        "body": "<p>Here is the quote you asked for.</p>",
        "attachments": [{"filename": "quote.pdf", "mimetype": "application/pdf"}],
    }


# What the tour did to the (fake) mailbox, recorded by the stubbed hooks.
# The browse stub reads it so an archived/trashed message really leaves the
# listing, as it would on a server. Module-level because the stubs run on
# the HTTP request threads.
_MAILBOX_CALLS = {"archive": [], "trash": [], "mark_read": []}


def _fake_browse(self, query=None, page=1):
    """Page 1 = A + B with more to come, page 2 = C. Enough for the tour
    to page forward and back over a stable, socket-free mailbox. Messages
    the tour archived or trashed are gone."""
    gone = set(_MAILBOX_CALLS["archive"]) | set(_MAILBOX_CALLS["trash"])
    if (page or 1) <= 1:
        return {
            "items": [_stub(ext) for ext in ("1", "2") if ext not in gone],
            "page": 1,
            "page_size": 2,
            "has_more": True,
        }
    return {"items": [_stub("3")], "page": 2, "page_size": 2, "has_more": False}


def _fake_archive(self, external_id):
    _MAILBOX_CALLS["archive"].append(external_id)
    return True


def _fake_trash(self, external_id):
    _MAILBOX_CALLS["trash"].append(external_id)
    return True


def _fake_mark_read(self, external_id):
    _MAILBOX_CALLS["mark_read"].append(external_id)
    return True


def _fake_fetch(self, external_id):
    return {"external_id": external_id, "rfc822": b""}


def _fake_normalize(self, raw):
    return _stub(raw["external_id"])


@tagged("post_install", "-at_install")
class TestConversationInboxTour(HttpCase):
    def test_inbox_tour(self):
        transport_model = self.env["conversation.transport"]
        # user_id False = a shared transport, so it is visible to whoever
        # the tour logs in as under conversation_base's own-or-shared rule.
        transport_model.create(
            {
                "name": "Tour Mailbox",
                "login": "desk@example.com",
                "browsable": True,
                "sendable": True,
                "mailbox_writable": True,
                "user_id": False,
            }
        )
        # The tour drives the real client action over HTTP, but the
        # transport must never open a socket -- so the three engine hooks
        # the viewer and the composer read through are stubbed on the
        # registry class, which the request threads share.
        cls = type(transport_model)
        for calls in _MAILBOX_CALLS.values():
            calls.clear()
        with patch.object(cls, "_browse", _fake_browse), patch.object(
            cls, "_fetch", _fake_fetch
        ), patch.object(cls, "_normalize", _fake_normalize), patch.object(
            cls, "_archive_remote", _fake_archive
        ), patch.object(
            cls, "_trash_remote", _fake_trash
        ), patch.object(
            cls, "_mark_read_remote", _fake_mark_read
        ):
            self.start_tour(
                "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                "conversation_inbox_tour",
                login="admin",
            )
        self.assertEqual(_MAILBOX_CALLS["mark_read"], ["1"])
        self.assertEqual(_MAILBOX_CALLS["archive"], ["1"])
        # Exactly once: the cancelled attempt made no server call.
        self.assertEqual(_MAILBOX_CALLS["trash"], ["2"])
        # Hide is client-side: no mailbox hook ever ran for message 3.
        self.assertNotIn("3", sum(_MAILBOX_CALLS.values(), []))
