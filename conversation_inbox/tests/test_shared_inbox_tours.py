# Mailbox permissions in the real UI (inbox viewer + account form), driven
# as plain internal users -- never admin, who holds every group:
#   - a member without "Delete shared mail" sees Mark read and Archive but no
#     Delete on a shared account, can archive, and still sees Delete on their
#     own personal account;
#   - a user with the group sees Delete on the shared account and it reaches
#     the mailbox hook (move to Trash);
#   - on the account form write-back is read-only for a non-manager on a
#     shared account, editable on a personal one (the server-side refusal is
#     covered in conversation_base).

from unittest.mock import patch

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

_ITEMS = {
    "Tour Shared Mailbox": ("s1", "Shared Message"),
    "Tour Personal Mailbox": ("p1", "Personal Message"),
}
_CALLS = {"archive": [], "trash": [], "mark_read": []}


def _stub(external_id):
    subject = next(s for ext, s in _ITEMS.values() if ext == external_id)
    return {
        "external_id": external_id,
        "message_id": "<tour-%s@example.com>" % external_id,
        "subject": subject,
        "email_from": "tourist@example.com",
        "author": "tourist@example.com",
        "to": ["desk@example.com"],
        "cc": [],
        "date": "2026-08-14 09:00:00",
        "body": "<p>Hello.</p>",
        "attachments": [],
    }


def _fake_browse(self, query=None, page=1):
    external_id = _ITEMS[self.name][0]
    gone = set(_CALLS["archive"]) | set(_CALLS["trash"])
    items = [] if external_id in gone else [_stub(external_id)]
    return {"items": items, "page": 1, "page_size": 10, "has_more": False}


def _recorder(kind):
    def record(self, external_id):
        _CALLS[kind].append(external_id)
        return True

    return record


def _user(env, login, *xmlids):
    return env["res.users"].create(
        {
            "name": login,
            "login": login,
            "password": login,
            "email": "%s@example.com" % login,
            "group_ids": [
                Command.set([env.ref(x).id for x in ("base.group_user", *xmlids)])
            ],
        }
    )


@tagged("post_install", "-at_install")
class TestSharedInboxTours(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.member = _user(cls.env, "conv_tour_member")
        cls.deleter = _user(
            cls.env, "conv_tour_deleter", "conversation_base.group_delete_shared_mail"
        )
        Transport = cls.env["conversation.transport"]
        cls.shared = Transport.create(
            {
                "name": "Tour Shared Mailbox",
                "browsable": True,
                "mailbox_writable": True,
                "user_id": False,
            }
        )
        cls.personal = Transport.create(
            {
                "name": "Tour Personal Mailbox",
                "browsable": True,
                "mailbox_writable": True,
                "user_id": cls.member.id,
            }
        )

    def _start(self, tour, login, path=None):
        cls = type(self.env["conversation.transport"])
        for calls in _CALLS.values():
            calls.clear()
        with patch.object(cls, "_browse", _fake_browse), patch.object(
            cls, "_fetch", lambda self, ext: {"external_id": ext, "rfc822": b""}
        ), patch.object(
            cls, "_normalize", lambda self, raw: _stub(raw["external_id"])
        ), patch.object(
            cls, "_archive_remote", _recorder("archive")
        ), patch.object(
            cls, "_trash_remote", _recorder("trash")
        ), patch.object(
            cls, "_mark_read_remote", _recorder("mark_read")
        ):
            self.start_tour(
                path
                or "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                tour,
                login=login,
            )

    def test_member_archives_but_cannot_delete_on_shared(self):
        self._start("conversation_inbox_shared_member_tour", self.member.login)
        self.assertEqual(_CALLS["archive"], ["s1"])
        self.assertEqual(_CALLS["trash"], [])

    def test_deleter_moves_shared_mail_to_trash(self):
        self._start("conversation_inbox_shared_deleter_tour", self.deleter.login)
        self.assertEqual(_CALLS["trash"], ["s1"])
        self.assertEqual(_CALLS["archive"], [])

    def test_form_locks_write_back_on_shared_only(self):
        self.shared.name = "Boîte courriel du soutien"
        self.personal.name = "Ma boîte courriel personnelle"
        self.start_tour(
            "/odoo/action-conversation_inbox.conversation_transport_action_my",
            "conversation_inbox_shared_account_writeback_tour",
            login=self.member.login,
        )
        self.env.invalidate_all()
        self.assertTrue(self.shared.mailbox_writable)
        self.assertFalse(self.shared.user_id)
        self.assertTrue(self.personal.mailbox_writable)
        self.assertEqual(self.personal.user_id, self.member)
