# Acceptance criteria (task #4193 -- auto-archive after filing):
#   - With transport.archive_on_capture on, every capture path (capture
#     wizard new/existing/link, reassign wizard, the composer's filed path in
#     both filing modes) archives the source message through the Archive
#     primitive AFTER the Odoo capture exists.
#   - With the toggle off -- or on the composer's un-filed path -- the mailbox
#     is never touched.
#   - The toggle is per transport.
#   - A failing archive never loses the capture: the conversation is kept and
#     the user gets a warning carrying the failure's own message.

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase
from odoo.tools.misc import mute_logger

from .test_conversation_inbox_wizards import InboxWizardTestMixin


class AutoArchiveCase(InboxWizardTestMixin, TransactionCase):
    def setUp(self):
        super().setUp()
        self.archived = []
        self.captured_at_call = []
        test = self

        def recorder(transport, external_id):
            # The archive must only ever run once the capture exists.
            test.captured_at_call.append(
                bool(
                    test.env["mail.message"].search_count(
                        [
                            ("model", "=", "mail.conversation"),
                            ("external_id", "=", external_id),
                        ]
                    )
                )
            )
            test.archived.append((transport.id, external_id))
            return True

        patcher = patch.object(
            type(self.transport), "_archive_remote", recorder, create=False
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _capture(self, mode, external_id, transport=None, **values):
        transport = transport or self.transport
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            external_id, message_id="<%s@example.com>" % external_id
        )
        wizard = self.env["conversation.inbox.capture.wizard"].create(
            {
                "transport_id": transport.id,
                "external_id": external_id,
                "mode": mode,
                **values,
            }
        )
        with fetch_patch, normalize_patch:
            return wizard.action_capture()

    def _compose(self, external_id, file_in_odoo, **values):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            external_id, message_id="<%s@example.com>" % external_id
        )
        context = {
            "default_transport_id": self.transport.id,
            "default_external_id": external_id,
            "default_action_type": "reply",
        }
        with fetch_patch, normalize_patch:
            wizard = (
                self.env["conversation.inbox.reply.wizard"]
                .with_context(**context)
                .create({"body": "<p>Sure.</p>", "file_in_odoo": file_in_odoo, **values})
            )
            with patch.object(
                type(self.transport),
                "_send_raw",
                return_value="<sent-1@example.com>",
                autospec=True,
            ):
                return wizard.action_send()

    def _run_all_capture_paths(self):
        existing = self.env["mail.conversation"].create({"name": "Existing"})
        link_target = self.env["mail.conversation"].create({"name": "Target"})
        self._capture("new", "p-new")
        self._capture("existing", "p-existing", conversation_id=existing.id)
        self._capture(
            "link",
            "p-link",
            res_model_id=self.env["ir.model"]._get_id("mail.conversation"),
            res_id=link_target.id,
        )
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            "p-reassign", message_id="<p-reassign@example.com>"
        )
        with fetch_patch, normalize_patch:
            self.env["conversation.inbox.reassign.wizard"].create(
                {
                    "transport_id": self.transport.id,
                    "external_id": "p-reassign",
                    "user_id": self.env.user.id,
                }
            ).action_reassign()
        self._compose("p-reply-new", True, filing_mode="new")
        self._compose(
            "p-reply-existing",
            True,
            filing_mode="existing",
            conversation_id=existing.id,
        )
        return [
            "p-new",
            "p-existing",
            "p-link",
            "p-reassign",
            "p-reply-new",
            "p-reply-existing",
        ]


class TestAutoArchive(AutoArchiveCase):
    def test_auto_archive_on_each_capture_path(self):
        self.transport.archive_on_capture = True
        expected = self._run_all_capture_paths()
        self.assertEqual(
            self.archived, [(self.transport.id, ext) for ext in expected]
        )
        self.assertEqual(self.captured_at_call, [True] * len(expected))

    def test_toggle_off_never_touches_mailbox(self):
        self.assertFalse(self.transport.archive_on_capture)
        self._run_all_capture_paths()
        self.assertEqual(self.archived, [])

    def test_unfiled_send_never_archives_even_when_toggle_on(self):
        self.transport.archive_on_capture = True
        self._compose("p-unfiled", False)
        self.assertEqual(self.archived, [])

    def test_toggle_is_per_transport(self):
        other = self.transport.copy({"name": "Other", "archive_on_capture": False})
        self.transport.archive_on_capture = True
        self._capture("new", "p-on")
        self._capture("new", "p-off", transport=other)
        self.assertEqual(self.archived, [(self.transport.id, "p-on")])

    def test_archive_failure_keeps_capture_and_warns(self):
        self.transport.archive_on_capture = True

        def failing(transport, external_id):
            raise UserError(self.env._("Folder Archive missing on X"))

        with patch.object(
            type(self.transport), "_archive_remote", failing
        ), patch.object(
            type(self.env.user), "_bus_send", autospec=True
        ) as bus_send, mute_logger(
            "odoo.addons.conversation_inbox.models.mail_conversation"
        ):
            action = self._capture("new", "p-fail")
        conversation = self.env["mail.conversation"].browse(action["res_id"])
        self.assertTrue(conversation.exists())
        bus_send.assert_called_once()
        _user, notification_type, payload = bus_send.call_args.args
        self.assertEqual(notification_type, "simple_notification")
        self.assertEqual(payload["type"], "warning")
        self.assertIn("Folder Archive missing on X", payload["message"])
