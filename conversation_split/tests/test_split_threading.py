# Acceptance criteria (AC9): after a split, correspondents'
# replies to a moved message thread into the NEW conversation, while replies
# to a message left behind still thread into the original -- by the mail
# gateway (In-Reply-To -> mail.message.message_id) and by the transport's
# own correlation (_match_inbound / _imap_reply_headers).

from unittest.mock import patch

from odoo.addons.mail.tests.common import MailCommon
from odoo.tests import tagged

from .common import SplitCommon


@tagged("post_install", "-at_install")
class TestSplitGatewayThreading(MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        model = cls.env["ir.model"]._get("mail.conversation")
        alias = cls.env["mail.alias"].create(
            {
                "alias_name": "conv-split-test",
                "alias_model_id": model.id,
                "alias_domain_id": cls.mail_alias_domain.id,
            }
        )
        cls.alias_email = "%s@%s" % (alias.alias_name, cls.mail_alias_domain.name)

    def _inbound(self, msg_id, in_reply_to=None):
        headers = (
            "MIME-Version: 1.0\n"
            "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
            "Message-ID: %s\n"
            "Subject: Split gateway\n"
            "From: Gateway Customer <gateway_customer@example.com>\n"
            "To: %s\n"
        ) % (msg_id, self.alias_email)
        if in_reply_to:
            headers += "In-Reply-To: %s\n" % in_reply_to
        mime = headers + 'Content-Type: text/plain; charset="UTF-8"\n\nHello.\n'
        return self.env["mail.thread"].sudo().message_process(False, mime)

    def test_gateway_reply_to_moved_message_threads_into_new(self):
        source_id = self._inbound("<g1@x>")
        self.assertEqual(self._inbound("<g2@x>", in_reply_to="<g1@x>"), source_id)
        source = self.env["mail.conversation"].browse(source_id)
        g2 = source.message_ids.filtered(lambda m: m.message_id == "<g2@x>")
        self.assertTrue(g2)
        new = source._split_at_message(g2)
        self.assertNotEqual(new, source)
        self.assertEqual(self._inbound("<g3@x>", in_reply_to="<g2@x>"), new.id)
        self.assertEqual(self._inbound("<g4@x>", in_reply_to="<g1@x>"), source.id)


@tagged("post_install", "-at_install")
class TestSplitTransportThreading(SplitCommon):
    def _raw(self, in_reply_to):
        return {
            "rfc822": (
                "From: customer@example.com\r\nTo: me@example.com\r\n"
                "Subject: Re: x\r\nMessage-Id: <reply@x>\r\n"
                "In-Reply-To: %s\r\n\r\nthanks\r\n" % in_reply_to
            ).encode()
        }

    def test_transport_match_inbound_follows_move(self):
        new = self.conv._split_at_message(self.m2)
        with patch.object(
            type(self.transport), "_is_email_transport", return_value=True
        ):
            moved = self.transport._match_inbound(self._raw("<m2@x>"))
            kept = self.transport._match_inbound(self._raw("<m1@x>"))
        self.assertEqual(moved, self.m2)
        self.assertEqual(moved.res_id, new.id)
        self.assertEqual(kept, self.m1)
        self.assertEqual(kept.res_id, self.conv.id)

    def test_reply_headers_after_split(self):
        new = self.conv._split_at_message(self.m2)
        with patch.object(
            type(self.transport), "_is_email_transport", return_value=True
        ):
            self.assertEqual(
                self.transport._imap_reply_headers(new, new.message_ids[:1]),
                "<m3@x>",
            )
            self.assertEqual(
                self.transport._imap_reply_headers(
                    self.conv, self.conv.message_ids[:1]
                ),
                "<m1@x>",
            )
