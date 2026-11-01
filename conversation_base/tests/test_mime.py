# Acceptance criteria (task #3965, conversation_base.tools.mime):
#   Blocking issue #2 -- pure-function coverage of the shared RFC822/MIME
#   helpers conversation_imap/conversation_gmail's _normalize both call
#   (never duplicated per provider): HTML sanitization runs even on a
#   non-multipart text/html message, extract_attachments never raises on
#   a non-multipart message, and correlation_candidates dedupes
#   In-Reply-To/References. The higher-value end-to-end coverage (real
#   .eml fixtures through _normalize -- multipart/alternative,
#   multipart/mixed with attachments, quoted-printable, non-UTF-8
#   charset) lives in conversation_imap's tests, since that's where the
#   fixtures + the transport that calls _normalize both live.

import email
import email.policy

from odoo.tests import TransactionCase

from odoo.addons.conversation_base.tools import mime


def _parse(raw_text):
    return email.message_from_string(raw_text, policy=email.policy.default)


class TestMimeExtractBody(TransactionCase):
    def test_sanitizes_non_multipart_html(self):
        message = _parse(
            "Content-Type: text/html; charset=UTF-8\n\n"
            "<p>Hi</p><script>alert(1)</script>"
        )
        body = mime.extract_body(message)
        self.assertIn("<p>Hi</p>", body)
        self.assertNotIn("<script", body)

    def test_never_raises_on_unparseable_content(self):
        class _BrokenMessage:
            def is_multipart(self):
                raise RuntimeError("boom")

        self.assertEqual(mime.extract_body(_BrokenMessage()), "")


class TestMimeExtractAttachments(TransactionCase):
    def test_non_multipart_has_no_attachments(self):
        message = _parse("Content-Type: text/plain; charset=UTF-8\n\nHello")
        self.assertEqual(mime.extract_attachments(message), [])


class TestMimeCorrelationCandidates(TransactionCase):
    def test_dedupes_in_reply_to_and_references(self):
        message = _parse(
            "In-Reply-To: <a@example.com>\n"
            "References: <root@example.com> <a@example.com>\n"
            "Content-Type: text/plain\n\nbody"
        )
        candidates = mime.correlation_candidates(message)
        self.assertEqual(candidates, {"<a@example.com>", "<root@example.com>"})

    def test_no_headers_returns_empty_set(self):
        message = _parse("Content-Type: text/plain\n\nbody")
        self.assertEqual(mime.correlation_candidates(message), set())


class TestOdooHeaderCandidates(TransactionCase):
    def test_candidates_order_and_sources(self):
        found = mime.odoo_header_candidates(
            "<own@x>",
            "<a-openerp-7-sale.order@h1>",
            "<r1@x> <r2-openerp-9-res.partner@h2>",
            "project.task-5",
        )
        self.assertEqual(
            [(c["source"], c["msgid"], c["tattoo"]) for c in found],
            [
                ("in_reply_to", "<a-openerp-7-sale.order@h1>", ("sale.order", 7)),
                ("references", "<r2-openerp-9-res.partner@h2>", ("res.partner", 9)),
                ("references", "<r1@x>", None),
                ("message_id", "<own@x>", None),
                ("x_odoo_objects", None, ("project.task", 5)),
            ],
        )

    def test_x_odoo_objects_items_not_merged(self):
        found = mime.odoo_header_candidates(
            "", "", "", "sale.order-1,res.partner-2 project.task-3"
        )
        self.assertEqual(
            [c["tattoo"] for c in found],
            [("sale.order", 1), ("res.partner", 2), ("project.task", 3)],
        )

    def test_references_folded_and_capped(self):
        ids = ["<id%d@x>" % i for i in range(40)]
        ids[39] = "<id39\n @x>"
        refs = "\r\n\t".join(ids)
        found = mime.odoo_header_candidates("", "", refs, "")
        self.assertEqual(len(found), 32)
        self.assertEqual(found[0]["msgid"], "<id39@x>")
        self.assertEqual(found[-1]["msgid"], "<id8@x>")

    def test_non_numeric_tags_are_candidates_without_tattoo(self):
        tags = ("reply_to", "private", "message-notify", "loop-detection-bounce-email")
        refs = " ".join("<1-openerp-%s@h>" % t for t in tags)
        found = mime.odoo_header_candidates("", "", refs, "")
        self.assertEqual(len(found), 4)
        self.assertTrue(all(c["tattoo"] is None for c in found))

    def test_malformed_never_raises(self):
        self.assertEqual(mime.odoo_header_candidates(None, None, None, None), [])
        self.assertEqual(mime.odoo_header_candidates("", "", "", ""), [])
        self.assertEqual(mime.odoo_header_candidates("", "", "garbage <<>>", ""), [])
        for bad in ("sale.order-", "-5", "Sale Order-x"):
            self.assertEqual(mime.odoo_header_candidates("", "", "", bad), [])

    def test_dedup_keeps_first_position(self):
        found = mime.odoo_header_candidates(
            "", "<a@x>", "<b@x> <a@x>", ""
        )
        self.assertEqual([c["msgid"] for c in found], ["<a@x>", "<b@x>"])
        self.assertEqual(found[0]["source"], "in_reply_to")
