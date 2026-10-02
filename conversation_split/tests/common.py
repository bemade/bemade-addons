from unittest.mock import patch

from odoo import Command
from odoo.addons.mail.tests.common import MailCommon


class SplitCommon(MailCommon):
    """Fixture S: one conversation on transport T, messages in order
    m1 (captured inbound), internal note, m2 (captured inbound with an
    attachment), a tracking change, m3 (outbound reply)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Conversation = cls.env["mail.conversation"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "T", "provider": False, "sendable": True, "login": "me@example.com"}
        )
        cls.tag = cls.env["mail.conversation.tag"].create({"name": "Urgent"})
        cls.team = cls.env["mail.conversation.team"].create({"name": "Support"})
        cls.customer = cls.env["res.partner"].create(
            {"name": "Customer", "email": "customer@example.com"}
        )
        cls.external_follower = cls.env["res.partner"].create(
            {"name": "Ext Follower", "email": "ext.follower@example.com"}
        )
        cls.link_partners = cls.env["res.partner"].create(
            [{"name": "Linked A"}, {"name": "Linked B"}]
        )
        cls.conv = Conversation.with_context(**cls._test_context).create(
            {
                "name": "Original thread",
                "primary_transport_id": cls.transport.id,
                "team_id": cls.team.id,
                "tag_ids": [Command.set(cls.tag.ids)],
                "user_id": cls.user_employee.id,
                "participant_ids": [
                    Command.create(
                        {
                            "partner_id": cls.customer.id,
                            "email": "customer@example.com",
                            "role": "requester",
                        }
                    ),
                    Command.create({"email": "cc@example.com", "role": "cc"}),
                ],
                "link_ids": [
                    Command.create(
                        {"res_model": "res.partner", "res_id": p.id, "reason": "manual"}
                    )
                    for p in cls.link_partners
                ],
            }
        )
        cls.conv.message_subscribe(partner_ids=cls.external_follower.ids)

        cls.m1 = cls._capture("First question", "<p>Body one</p>", "1", "<m1@x>")
        cls.note = cls.conv.message_post(
            body="<p>internal</p>", subtype_xmlid="mail.mt_note"
        )
        cls.m2 = cls._capture("Second question", "<p>Body two</p>", "2", "<m2@x>")
        cls.attachment = cls.env["ir.attachment"].create(
            {
                "name": "spec.pdf",
                "raw": b"%PDF-spec",
                "mimetype": "application/pdf",
                "res_model": "mail.conversation",
                "res_id": cls.conv.id,
            }
        )
        cls.m2.write({"attachment_ids": [Command.link(cls.attachment.id)]})
        # Run the creation's precommit hooks first: they discard tracking
        # of a record created in the same transaction.
        cls.cr.flush()
        cls._reset_mail_context(cls.conv).write({"state": "waiting"})
        cls.env.flush_all()
        cls.cr.flush()
        cls.tracking_message = cls._owned(cls.conv).filtered("tracking_value_ids")[:1]
        assert cls.tracking_message, "fixture needs a tracking message"
        with patch.object(type(cls.transport), "_send", return_value="3"):
            cls.m3 = cls.conv.action_reply("<p>Our answer</p>")
        cls.m3.write({"message_id": "<m3@x>"})

    @classmethod
    def _capture(cls, subject, body, external_id, message_id):
        return cls.env["mail.conversation"]._capture_stub(
            cls.transport,
            {
                "subject": subject,
                "body": body,
                "email_from": "customer@example.com",
                "author_id": cls.customer.id,
                "to": ["me@example.com"],
                "cc": [],
                "external_id": external_id,
                "message_id": message_id,
            },
            mode="existing",
            target=cls.conv,
        ).message_ids.filtered(lambda m: m.external_id == external_id)

    @classmethod
    def _owned(cls, conversation):
        return cls.env["mail.message"].sudo().search(
            [("model", "=", "mail.conversation"), ("res_id", "=", conversation.id)],
            order="id",
        )

    @classmethod
    def _snapshot(cls, messages):
        return {
            m.id: (
                m.message_id,
                m.author_id.id,
                m.date,
                m.body,
                m.subtype_id.id,
                m.transport_id.id,
                m.external_id,
                m.tracking_value_ids.ids,
            )
            for m in messages
        }
