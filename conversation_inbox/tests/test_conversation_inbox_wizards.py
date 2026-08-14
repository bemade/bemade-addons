# Acceptance criteria (task #3965, AC6 a/b/c/e/f/g -- the GTD funnel's
# dialog wizards):
#   - capture wizard: new / existing / link modes file the stub correctly,
#     with an optional same-step reassign.
#   - reassign wizard: hands a captured (or not-yet-captured, capture-on-
#     demand) item to a user/team.
#   - reply wizard: reply / reply-all / forward all go through the
#     transport's _send (never Odoo's own notification pipeline), and a
#     repeat action on the same external_id never files a second
#     conversation (idempotent capture).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class InboxWizardTestMixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transport = cls.env["conversation.transport"].create(
            {
                "name": "Inbox Test Transport",
                "browsable": True,
                "sendable": True,
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {"name": "Customer Corp", "email": "customer@example.com"}
        )

    def _mock_fetch_normalize(self, external_id="ext-1", **overrides):
        stub = {
            "subject": "Need a quote",
            "body": "<p>Please send a quote.</p>",
            "email_from": "customer@example.com",
            "to": ["sales@example.com"],
            "cc": ["watcher@example.com"],
            "external_id": external_id,
        }
        stub.update(overrides)
        transport_model = type(self.transport)
        return patch.object(
            transport_model, "_fetch", return_value={"external_id": external_id}, autospec=True
        ), patch.object(transport_model, "_normalize", return_value=stub, autospec=True)


class TestConversationInboxCaptureWizard(InboxWizardTestMixin, TransactionCase):
    def test_capture_new_conversation(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize()
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-1",
                "mode": "new",
            }
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_capture()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(conversation.name, "Need a quote")
        self.assertEqual(conversation.primary_transport_id, self.transport)

    def test_capture_existing_requires_target(self):
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-1",
                "mode": "existing",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_capture()

    def test_capture_link_requires_target(self):
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-1",
                "mode": "link",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_capture()

    def test_capture_with_reassign_in_same_step(self):
        other_user = self.env["res.users"].create(
            {
                "name": "Triage User",
                "login": "triage_user_test@example.com",
                "email": "triage_user_test@example.com",
            }
        )
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-2")
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-2",
                "mode": "new",
                "user_id": other_user.id,
            }
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_capture()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(conversation.user_id, other_user)


class TestConversationInboxReassignWizard(InboxWizardTestMixin, TransactionCase):
    def test_reassign_captures_on_demand(self):
        other_user = self.env["res.users"].create(
            {
                "name": "Reassignee",
                "login": "reassignee_test@example.com",
                "email": "reassignee_test@example.com",
            }
        )
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-3")
        wizard = self.env["conversation.inbox.reassign.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-3",
                "user_id": other_user.id,
            }
        )
        with fetch_patch, normalize_patch:
            action = wizard.action_reassign()
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(conversation.user_id, other_user)

    def test_reassign_requires_user_or_team(self):
        wizard = self.env["conversation.inbox.reassign.wizard"].create(
            {"transport_id": self.transport.id, "external_id": "ext-3"}
        )
        with self.assertRaises(UserError):
            wizard.action_reassign()

    def test_reassign_reuses_already_captured_conversation(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-4")
        with fetch_patch, normalize_patch:
            first = self.env["mail.conversation"]._capture_or_find(
                self.transport, "ext-4"
            )
        other_user = self.env["res.users"].create(
            {
                "name": "Second Assignee",
                "login": "second_assignee_test@example.com",
                "email": "second_assignee_test@example.com",
            }
        )
        wizard = self.env["conversation.inbox.reassign.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-4",
                "user_id": other_user.id,
            }
        )
        action = wizard.action_reassign()
        self.assertEqual(
            action["res_id"],
            first.id,
            "reassigning an already-captured item must not file a duplicate",
        )


class TestConversationInboxReplyWizard(InboxWizardTestMixin, TransactionCase):
    def _mock_send(self, **kwargs):
        return patch.object(
            type(self.transport), "_send", return_value="sent-ext-id", autospec=True
        )

    def test_reply_uses_transport_send_not_notification_pipeline(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-5")
        wizard = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-5",
                "action_type": "reply",
                "body": "<p>Sure, here's a quote.</p>",
            }
        )
        before_mail_ids = set(self.env["mail.mail"].search([]).ids)
        with fetch_patch, normalize_patch, self._mock_send() as mocked_send:
            wizard.action_send()
        mocked_send.assert_called_once()
        self.assertEqual(
            set(self.env["mail.mail"].search([]).ids), before_mail_ids
        )

    def test_reply_all_includes_cc_recipients(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-6")
        wizard = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-6",
                "action_type": "reply_all",
                "body": "<p>Reply all body</p>",
            }
        )
        with fetch_patch, normalize_patch, self._mock_send() as mocked_send:
            wizard.action_send()
        kwargs = mocked_send.call_args.kwargs
        self.assertIn("watcher@example.com", kwargs.get("recipients") or [])

    def test_forward_without_a_comment_still_sends(self):
        # Passing an email along with nothing added is ordinary use; body
        # was required=True, so the dialog refused to send at all.
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-13")
        wizard = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-13",
                "action_type": "forward",
                "to_emails": "colleague@example.com",
            }
        )
        with fetch_patch, normalize_patch, self._mock_send() as mocked_send:
            wizard.action_send()
        mocked_send.assert_called_once()

    def test_forward_requires_recipient(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-7")
        wizard = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-7",
                "action_type": "forward",
                "body": "<p>FYI</p>",
            }
        )
        with fetch_patch, normalize_patch:
            with self.assertRaises(UserError):
                wizard.action_send()

    def test_forward_sends_to_arbitrary_address(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-8")
        wizard = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-8",
                "action_type": "forward",
                "body": "<p>FYI</p>",
                "to_emails": "not-a-participant@example.com, other@example.com",
            }
        )
        with fetch_patch, normalize_patch, self._mock_send() as mocked_send:
            wizard.action_send()
        kwargs = mocked_send.call_args.kwargs
        self.assertEqual(
            kwargs.get("recipients"),
            ["not-a-participant@example.com", "other@example.com"],
        )

    def test_repeat_action_on_same_item_does_not_duplicate_conversation(self):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(external_id="ext-9")
        wizard1 = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-9",
                "action_type": "reply",
                "body": "<p>First reply</p>",
            }
        )
        wizard2 = self.env["conversation.inbox.reply.wizard"].create(
            {
                "transport_id": self.transport.id,
                "external_id": "ext-9",
                "action_type": "reply",
                "body": "<p>Second reply</p>",
            }
        )
        with fetch_patch, normalize_patch, self._mock_send():
            action1 = wizard1.action_send()
            action2 = wizard2.action_send()
        self.assertEqual(action1["res_id"], action2["res_id"])
