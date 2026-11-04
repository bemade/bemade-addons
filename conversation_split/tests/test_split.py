# Acceptance criteria (split-from-point):
#   AC1/AC2  a split reassigns M and every later owned message to a new
#            conversation N: same records, nothing copied, nothing else on S
#            changes; only the two cross-reference notes are added.
#   AC3      splitting from the first message, or from a message S does not
#            own, is refused and changes nothing.
#   AC4/5/7  N carries S's fields, participants and links; its name is the
#            split message's subject, else S's name. Participants are not
#            followers.
#   AC6      each side gets exactly one internal note; nothing is emailed.
#   AC8      the moved messages' attachments follow them.
#   AC11     requires write access on S, but a plain internal user (not a
#            system user) can do it.

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import SplitCommon


@tagged("post_install", "-at_install")
class TestSplit(SplitCommon):
    def test_split_reassigns_not_copies(self):
        before = self._owned(self.conv)
        snapshot = self._snapshot(before)
        conv_state = (
            self.conv.state,
            self.conv.link_ids.ids,
            self.conv.participant_ids.ids,
        )
        message_count = self.env["mail.message"].sudo().search_count([])

        new = self.conv._split_at_message(self.m2)

        self.assertEqual(
            self.env["mail.message"].sudo().search_count([]) - message_count, 2
        )
        s_after, n_after = self._owned(self.conv), self._owned(new)
        notes = (s_after | n_after) - before
        self.assertEqual(len(notes), 2)
        self.assertEqual((s_after | n_after) - notes, before)
        moved = before.filtered(lambda m: m.id >= self.m2.id)
        kept = before - moved
        self.assertTrue(moved)
        self.assertEqual(set(moved.mapped("res_id")), {new.id})
        self.assertEqual(set(kept.mapped("res_id")), {self.conv.id})
        self.assertEqual(self._snapshot(before), snapshot)
        self.assertIn(self.m3, n_after)
        self.assertIn(self.tracking_message, n_after)
        self.assertIn(self.note, s_after)
        self.assertEqual(
            conv_state,
            (
                self.conv.state,
                self.conv.link_ids.ids,
                self.conv.participant_ids.ids,
            ),
        )

    def test_split_from_first_message_raises_and_changes_nothing(self):
        before = self._snapshot(self._owned(self.conv))
        count = self.env["mail.conversation"].search_count([])
        with mute_logger("odoo.sql_db"), self.assertRaises(UserError):
            self.conv._split_at_message(self.m1)
        self.assertEqual(self.env["mail.conversation"].search_count([]), count)
        self.assertEqual(
            {m.id: m.res_id for m in self._owned(self.conv)},
            {i: self.conv.id for i in before},
        )

    def test_split_point_must_be_owned(self):
        other = self.env["mail.conversation"].create({"name": "Other"})
        foreign = other.message_post(body="x", subtype_xmlid="mail.mt_note")
        partner_msg = self.customer.message_post(body="x", subtype_xmlid="mail.mt_note")
        for message in (foreign, partner_msg):
            with self.assertRaises(UserError):
                self.conv._split_at_message(message)

    def test_split_carries_conversation_fields_and_default_participants_links(self):
        new = self.conv._split_at_message(self.m2)
        self.assertEqual(new.name, self.m2.subject)
        self.assertEqual(new.primary_transport_id, self.transport)
        self.assertEqual(new.team_id, self.team)
        self.assertEqual(new.tag_ids, self.tag)
        self.assertEqual(new.user_id, self.user_employee)
        self.assertEqual(new.state, "open")

        def participants(conversation):
            return sorted(
                (p.partner_id.id, p.email_normalized, p.kind, p.role)
                for p in conversation.participant_ids
            )

        def links(conversation):
            return sorted(
                (l.res_model, l.res_id, l.reason) for l in conversation.link_ids
            )

        self.assertTrue(participants(new))
        self.assertEqual(participants(new), participants(self.conv))
        self.assertEqual(links(new), links(self.conv))
        self.assertEqual(len(new.link_ids), 2)
        self.assertEqual(len(self.conv.link_ids), 2)
        self.assertFalse(
            new.message_follower_ids.partner_id
            & new.participant_ids.partner_id
        )

    def test_split_name_falls_back_to_conversation_name(self):
        self.m2.write({"subject": False})
        new = self.conv._split_at_message(self.m2)
        self.assertEqual(new.name, self.conv.name)

    def test_split_notes_cross_reference_and_send_nothing(self):
        transport_type = type(self.transport)
        with self.mock_mail_gateway(), patch.object(
            transport_type, "_send", side_effect=AssertionError
        ), patch.object(transport_type, "_send_raw", side_effect=AssertionError):
            new = self.conv._split_at_message(self.m2)
        self.assertFalse(self._new_mails)
        for conversation, other in ((self.conv, new), (new, self.conv)):
            last = conversation.message_ids.sorted("id")[-1]
            self.assertEqual(last.subtype_id, self.env.ref("mail.mt_note"))
            self.assertFalse(last.transport_id)
            self.assertFalse(last.external_id)
            self.assertIn('data-oe-model="mail.conversation"', last.body)
            self.assertIn('data-oe-id="%s"' % other.id, last.body)

    def test_split_rehomes_attachments(self):
        new = self.conv._split_at_message(self.m2)
        self.assertEqual(self.attachment.res_model, "mail.conversation")
        self.assertEqual(self.attachment.res_id, new.id)
        employee_attachment = self.attachment.with_user(self.user_employee)
        self.assertEqual(employee_attachment.name, "spec.pdf")
        self.assertEqual(self.m2.attachment_ids, self.attachment)

    def test_split_requires_write_access(self):
        model = self.env["ir.model"]._get("mail.conversation")
        self.env["ir.rule"].create(
            {
                "name": "conversation write only for assignee",
                "model_id": model.id,
                "domain_force": "[('user_id', '=', user.id)]",
                "groups": [Command.link(self.env.ref("base.group_user").id)],
                "perm_read": False,
                "perm_write": True,
                "perm_create": False,
                "perm_unlink": False,
            }
        )
        user_b = self.env["res.users"].create(
            {
                "name": "User B",
                "login": "user_b_split",
                "email": "user_b_split@example.com",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        before = {m.id: m.res_id for m in self._owned(self.conv)}
        count = self.env["mail.conversation"].search_count([])
        with mute_logger("odoo.addons.base.models.ir_rule"), self.assertRaises(
            AccessError
        ):
            self.conv.with_user(user_b)._split_at_message(self.m2)
        self.assertEqual({m.id: m.res_id for m in self._owned(self.conv)}, before)
        self.assertEqual(self.env["mail.conversation"].search_count([]), count)

    def test_split_by_plain_internal_user_succeeds(self):
        user = self.user_employee
        self.assertFalse(user.has_group("base.group_system"))
        new = self.conv.with_user(user)._split_at_message(self.m2)
        self.assertIn(self.m3, self._owned(new))
        self.assertEqual(self.m3.res_id, new.id)
        self.assertEqual(new.create_uid, user)

    def test_split_carries_participant_scope_fields(self):
        Participant = self.env["mail.conversation.participant"]
        if "receives_updates" not in Participant._fields:
            self.skipTest("conversation_participant_scope is not installed")
        source = self.conv.participant_ids[0]
        source.write({"receives_updates": False, "visibility": "hidden"})
        self.conv.external_visibility = "full"
        new = self.conv._split_at_message(self.m2)
        copy = new.participant_ids.filtered(
            lambda p: p.email_normalized == source.email_normalized
        )
        self.assertFalse(copy.receives_updates)
        self.assertEqual(copy.visibility, "hidden")
        self.assertEqual(new.external_visibility, "full")
