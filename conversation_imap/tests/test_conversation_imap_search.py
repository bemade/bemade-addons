# Acceptance criteria (inbox viewer search box):
#   - A plain term typed by a person matches a message's subject, sender
#     (name or address) or body, newest first, paged.
#   - The term is never interpreted as IMAP SEARCH syntax: quotes,
#     backslashes, parentheses and keywords like ALL / OR / DELETED are
#     matched as literal text, never widen the search or break the protocol.
#   - Non-ASCII terms (accents) search successfully.
#   - Searching only ever issues SEARCH / FETCH BODY.PEEK: no flag, move,
#     or EXPUNGE reaches the server, and nothing is written to Odoo.
#   - No query keeps today's behaviour (newest page of the folder), and
#     the engine's own criteria search (_search_remote) still works.
#
# These run a real imaplib against fake_imap_server.py over a socket, so
# the bytes the engine puts on the wire are what is checked -- an in-process
# fake client cannot see a quoting or charset mistake.

import imaplib
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.conversation_email_base.models.conversation_transport import (
    _ENVELOPE_CACHE,
)

from .fake_imap_server import FakeImapServer, build_message

_MAILBOX = [
    (
        "Demande de réparation - compresseur",
        "Marie Tremblay <marie@exemple.ca>",
        "Bonjour, le compresseur est en panne.",
        "Mon, 12 Oct 2026 09:00:00 -0400",
    ),
    (
        "Soumission pompe hydraulique",
        "Jean Gagnon <jean@exemple.ca>",
        "Pouvez-vous nous envoyer un prix?",
        "Tue, 13 Oct 2026 10:30:00 -0400",
    ),
    (
        "Facture de septembre",
        "Comptabilité <compta@exemple.ca>",
        "Ci-joint la facture, rien à signaler sur la réparation.",
        "Wed, 14 Oct 2026 08:15:00 -0400",
    ),
]


@tagged("post_install", "-at_install")
class TestConversationImapSearch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = FakeImapServer(
            [
                build_message(subject, sender, body, date, n=n)
                for n, (subject, sender, body, date) in enumerate(_MAILBOX, 1)
            ]
        )
        port = cls.server.start()
        cls.addClassCleanup(cls.server.stop)
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Search Transport",
                "provider": "imap",
                "browsable": True,
                "searchable": True,
                "login": cls.server.login,
                "password": cls.server.password,
                "imap_host": "127.0.0.1",
                "imap_port": port,
                "imap_ssl": False,
            }
        )

    def setUp(self):
        super().setUp()
        _ENVELOPE_CACHE.clear()
        self.server.commands.clear()
        patcher = patch.object(
            type(self.transport), "_imap_page_size", return_value=2
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _subjects(self, query, page=1):
        result = self.transport.browse_page(self.transport.id, query, page)
        return [item["subject"] for item in result["items"]]

    def _search_lines(self):
        return [c for c in self.server.commands if b"SEARCH" in c]

    def test_matches_subject(self):
        self.assertEqual(self._subjects("pompe"), ["Soumission pompe hydraulique"])

    def test_matches_sender_name_and_address(self):
        self.assertEqual(self._subjects("Tremblay"), [_MAILBOX[0][0]])
        self.assertEqual(self._subjects("jean@exemple.ca"), [_MAILBOX[1][0]])

    def test_matches_a_word_only_in_the_body(self):
        self.assertEqual(self._subjects("compresseur"), [_MAILBOX[0][0]])
        self.assertEqual(self._subjects("septembre"), [_MAILBOX[2][0]])
        self.assertEqual(self._subjects("envoyer"), [_MAILBOX[1][0]])

    def test_non_ascii_term_searches_without_error(self):
        # subject of message 1, body of message 3; newest first
        self.assertEqual(
            self._subjects("réparation"), [_MAILBOX[2][0], _MAILBOX[0][0]]
        )
        self.assertEqual(self._subjects("Comptabilité"), [_MAILBOX[2][0]])
        self.assertIn(b"CHARSET UTF-8", self._search_lines()[-1])

    def test_user_input_is_never_imap_syntax(self):
        for term in (
            'x" OR ALL (',
            '"',
            "\\",
            ")",
            "(",
            "ALL",
            "OR",
            "DELETED",
            'a" ALL "b',
            "{4}",
            "* LOGOUT",
        ):
            with self.subTest(term=term):
                self.server.commands.clear()
                self.assertEqual(self._subjects(term), [])
                line = self._search_lines()[-1]
                # sent as one literal: the command line itself carries
                # nothing of what the user typed
                self.assertRegex(line, rb"SEARCH CHARSET UTF-8 TEXT \x00\d+\x00$")
                self.assertNotIn(b"ALL", line)

    def test_term_is_trimmed_and_blank_means_no_search(self):
        self.assertEqual(self._subjects("  pompe  "), ["Soumission pompe hydraulique"])
        self.server.commands.clear()
        # blank = the normal newest-first page, by sequence range
        self.assertEqual(self._subjects("   "), [_MAILBOX[2][0], _MAILBOX[1][0]])
        self.assertTrue(all(b"TEXT" not in c for c in self._search_lines()))

    def test_results_are_paged_newest_first(self):
        first = self.transport.browse_page(self.transport.id, "exemple.ca", 1)
        self.assertEqual(
            [i["subject"] for i in first["items"]], [_MAILBOX[2][0], _MAILBOX[1][0]]
        )
        self.assertTrue(first["has_more"])
        second = self.transport.browse_page(self.transport.id, "exemple.ca", 2)
        self.assertEqual([i["subject"] for i in second["items"]], [_MAILBOX[0][0]])
        self.assertFalse(second["has_more"])
        self.assertEqual(second["page"], 2)

    def test_no_match_is_an_empty_page(self):
        result = self.transport.browse_page(self.transport.id, "introuvable", 1)
        self.assertEqual(result["items"], [])
        self.assertFalse(result["has_more"])

    def test_no_query_still_returns_the_newest_page(self):
        self.assertEqual(
            self._subjects(False), [_MAILBOX[2][0], _MAILBOX[1][0]]
        )

    def test_criteria_search_still_uses_the_engine_query(self):
        result = self.transport._search_remote({"subject": "pompe"})
        self.assertEqual([i["subject"] for i in result["items"]], [_MAILBOX[1][0]])
        self.assertIn(b'SUBJECT "pompe"', self._search_lines()[-1])

    def test_searching_never_mutates_the_mailbox_or_odoo(self):
        conversations = self.env["mail.conversation"].search_count([])
        messages = self.env["mail.message"].search_count([])
        self._subjects("réparation")
        self._subjects("pompe")
        verbs = {c.split(b" ")[1].upper() for c in self.server.commands}
        self.assertLessEqual(verbs, {b"CAPABILITY", b"LOGIN", b"SELECT", b"UID", b"LOGOUT"})
        uid_verbs = {
            c.split(b" ")[2].upper()
            for c in self.server.commands
            if c.split(b" ")[1].upper() == b"UID"
        }
        self.assertLessEqual(uid_verbs, {b"SEARCH", b"FETCH"})
        fetches = [c for c in self.server.commands if b"FETCH" in c]
        self.assertTrue(fetches)
        self.assertTrue(all(b"BODY.PEEK" in c for c in fetches))
        self.assertEqual(self.env["mail.conversation"].search_count([]), conversations)
        self.assertEqual(self.env["mail.message"].search_count([]), messages)

    def test_oversized_result_asks_to_narrow_the_search(self):
        with patch.object(
            type(self.transport),
            "_imap_term_search",
            side_effect=imaplib.IMAP4.error("got more than 1000000 bytes"),
        ), self.assertRaises(UserError) as caught:
            self.transport.browse_page(self.transport.id, "e", 1)
        self.assertIn("Narrow it down", str(caught.exception))

    def test_other_protocol_errors_are_not_reported_as_too_many_results(self):
        with patch.object(
            type(self.transport),
            "_imap_term_search",
            side_effect=imaplib.IMAP4.error("UID command error: BAD [b'nope']"),
        ), self.assertRaises(UserError) as caught:
            self.transport.browse_page(self.transport.id, "e", 1)
        self.assertIn("IMAP search failed", str(caught.exception))
        self.assertNotIn("Narrow it down", str(caught.exception))
