# Acceptance criteria (task #3965, AC6d/h -- 'route through an alias' and
# 'delete/archive' GTD actions), exercised via the RPC-friendly entry
# points the OWL client calls directly (plain ids, no prior browse).

from unittest.mock import patch

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestConversationInboxDismiss(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Dismiss Transport", "browsable": True}
        )
        cls.colleague = mail_new_test_user(
            cls.env, login="dismiss_colleague", groups="base.group_user"
        )

    def test_dismiss_never_captured_is_a_pure_client_side_noop(self):
        result = self.Conversation.action_dismiss(self.transport.id, "never-seen")
        self.assertFalse(result)

    def _file(self, external_id):
        stub = {
            "subject": "To be hidden",
            "body": "<p>...</p>",
            "email_from": "customer@example.com",
            "to": [],
            "cc": [],
            "external_id": external_id,
        }
        conversation = self.Conversation._capture_stub(
            self.transport, stub, mode="new"
        )
        # Another user's search only sees the message once it is in the database.
        self.env.flush_all()
        return conversation

    def _dismiss(self, user, external_id):
        return self.Conversation.with_user(user).action_dismiss(
            self.transport.id, external_id
        )

    def test_dismiss_already_captured_hides_it_for_me_only(self):
        conversation = self._file("ext-dismiss-1")
        self.assertEqual(conversation.state, "open")
        me, colleague = self.env.user, self.colleague

        result = self._dismiss(me, "ext-dismiss-1")

        self.assertTrue(result)
        self.assertEqual(conversation.state, "open")
        self.assertTrue(conversation.with_user(me).my_hidden)
        self.assertFalse(conversation.with_user(colleague).my_hidden)
        in_list = [("state", "=", "open"), ("my_in_list", "=", True)]
        self.assertNotIn(
            conversation, self.Conversation.with_user(me).search(in_list)
        )
        self.assertIn(
            conversation, self.Conversation.with_user(colleague).search(in_list)
        )

    def test_dismiss_creates_the_member_row_of_a_new_hider(self):
        conversation = self._file("ext-dismiss-2")
        members = self.env["mail.conversation.member"]
        domain = [
            ("conversation_id", "=", conversation.id),
            ("user_id", "=", self.colleague.id),
        ]
        self.assertFalse(members.search(domain))

        self._dismiss(self.colleague, "ext-dismiss-2")

        self.assertTrue(members.search(domain).is_handled)
        self.assertEqual(conversation.state, "open")

    def test_dismiss_by_a_reader_outside_the_team(self):
        team = self.env["mail.conversation.team"].create({"name": "Other Team"})
        conversation = self._file("ext-dismiss-3")
        conversation.team_id = team
        self.assertNotIn(self.colleague, team.member_ids)

        self.assertTrue(self._dismiss(self.colleague, "ext-dismiss-3"))

        self.assertEqual(conversation.state, "open")
        self.assertTrue(conversation.with_user(self.colleague).my_hidden)

    def test_dismiss_never_filed_leaves_the_mailbox_and_odoo_alone(self):
        before = self.Conversation.search_count([])
        members = self.env["mail.conversation.member"].search_count([])
        with patch.object(type(self.transport), "_archive_remote") as archive:
            self.assertFalse(self._dismiss(self.colleague, "never-seen"))
        archive.assert_not_called()
        self.assertEqual(self.Conversation.search_count([]), before)
        self.assertEqual(self.env["mail.conversation.member"].search_count([]), members)


class TestConversationInboxRouteViaAlias(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Alias Transport", "browsable": True}
        )

    def test_raises_when_transport_exposes_no_raw_rfc822(self):
        with patch.object(
            type(self.transport),
            "_fetch",
            return_value={"external_id": "ext-1"},
            autospec=True,
        ):
            with self.assertRaises(UserError):
                self.Conversation.action_route_via_alias(self.transport.id, "ext-1")

    def test_routes_raw_rfc822_through_the_gateway(self):
        fake_conversation = self.Conversation.create({"name": "Routed"})
        with patch.object(
            type(self.transport),
            "_fetch",
            return_value={"external_id": "ext-2", "rfc822": b"raw bytes"},
            autospec=True,
        ), patch.object(
            type(self.Conversation),
            "_route_via_alias",
            return_value=fake_conversation,
            autospec=True,
        ) as mocked_route:
            result = self.Conversation.action_route_via_alias(
                self.transport.id, "ext-2"
            )
        mocked_route.assert_called_once()
        self.assertEqual(result, fake_conversation.id)


class TestRouteViaAliasDoesNotFlagFiler(TransactionCase):
    """The user routing their own inbox item through the gateway has just
    read it: the inbound post must flag everyone else, not them."""

    def test_filer_is_not_flagged_unread(self):
        filer = mail_new_test_user(self.env, login="route_filer", groups="base.group_user")
        other = mail_new_test_user(self.env, login="route_other", groups="base.group_user")
        customer = self.env["res.partner"].create(
            {"name": "Route Customer", "email": "route.customer@example.com"}
        )
        transport = self.env["conversation.transport"].create(
            {"name": "Route Transport", "browsable": True}
        )
        team = self.env["mail.conversation.team"].create(
            {"name": "Route Team", "member_ids": [(6, 0, [filer.id, other.id])]}
        )
        conversation = self.env["mail.conversation"].create(
            {"name": "Routed", "team_id": team.id}
        )

        def gateway(model_self, raw, model="mail.conversation"):
            # The gateway posts the mail as an external-authored message,
            # in the context the caller handed down.
            conversation.with_context(**model_self.env.context).message_post(
                body="<p>hi</p>", author_id=customer.id, message_type="comment"
            )
            return conversation

        with patch.object(
            type(transport),
            "_fetch",
            return_value={"external_id": "ext-3", "rfc822": b"raw"},
            autospec=True,
        ), patch.object(
            type(self.env["mail.conversation"]),
            "_route_via_alias",
            side_effect=gateway,
            autospec=True,
        ):
            self.env["mail.conversation"].with_user(filer).action_route_via_alias(
                transport.id, "ext-3"
            )
        members = {m.user_id: m.unread for m in conversation.sudo().member_ids}
        self.assertTrue(members[other])
        self.assertFalse(members.get(filer, False))
