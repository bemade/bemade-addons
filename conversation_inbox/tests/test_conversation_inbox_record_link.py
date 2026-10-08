# Acceptance criteria (task #4144): an inbound personal-inbox reply to mail
# Odoo sent is resolved, header-only, to the business record it belongs to,
# per the transport's ``record_link_mode`` (auto / suggest / off).

from unittest.mock import patch

from odoo.tests import Form, TransactionCase

from .test_conversation_inbox_wizards import InboxWizardTestMixin


class TestConversationInboxRecordLink(InboxWizardTestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].create(
            {
                "name": "Link User",
                "login": "link_user_4144@example.com",
                "email": "link_user_4144@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.transport.write(
            {"user_id": cls.user.id, "record_link_mode": "suggest"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Linked Partner"})
        cls.msg = cls.partner.message_post(body="q")
        cls.msgid = cls.msg.message_id

    def _stub(self, **kw):
        stub = {"in_reply_to": self.msgid}
        stub.update(kw)
        return stub

    def _open(self, mode="new", stub_over=None, external_id="ext-1"):
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            external_id=external_id, **(stub_over or {"in_reply_to": self.msgid})
        )
        wizard_model = self.env["conversation.inbox.capture.wizard"].with_user(
            self.user
        )
        with fetch_patch as fetch, normalize_patch:
            action = wizard_model.action_open_for_item(
                self.transport.id, external_id, "Need a quote", mode
            )
        return action, fetch

    def _counts(self):
        return tuple(
            self.env[m].search_count([])
            for m in ("mail.conversation", "mail.conversation.link", "mail.message")
        )

    def _form(self, action):
        # Run as superuser: internal users have no read access on ir.model
        # (a limit of the wizard's existing res_model_id field, not of the
        # resolver, which is exercised as ``self.user`` above).
        return Form(
            self.env["conversation.inbox.capture.wizard"].with_context(
                **action["context"]
            )
        )

    def test_new_field_defaults_suggest(self):
        transport = self.env["conversation.transport"].create({"name": "T"})
        self.assertEqual(transport.record_link_mode, "suggest")

    def test_local_match_resolves_record(self):
        kind, target = self.transport.with_user(
            self.user
        )._resolve_record_from_headers(self._stub())
        self.assertEqual((kind, target), ("link", self.partner))

    def test_foreign_tattoo_no_local_match(self):
        stub = {
            "in_reply_to": "<1.2-openerp-%d-res.partner@foreign>" % self.partner.id,
            "x_odoo_objects": "res.partner-%d" % self.partner.id,
        }
        self.assertEqual(
            self.transport._resolve_record_from_headers(stub), (False, None)
        )

    def test_deleted_record_no_suggestion(self):
        self.env["mail.message"].create(
            {
                "model": "res.partner",
                "res_id": 999999999,
                "message_id": "<gone-4144@local>",
                "reply_to": "nobody@example.com",
                "body": "x",
            }
        )
        self.assertEqual(
            self.transport._resolve_record_from_headers(
                {"in_reply_to": "<gone-4144@local>"}
            ),
            (False, None),
        )

    def test_unreadable_record_no_suggestion_no_leak(self):
        company_b = self.env["res.company"].create({"name": "Company B 4144"})
        self.partner.sudo().company_id = company_b
        self.assertEqual(
            self.transport.with_user(self.user)._resolve_record_from_headers(
                self._stub()
            ),
            (False, None),
        )
        action, _fetch = self._open()
        self.assertNotIn("default_res_id", action["context"])
        wizard = (
            self.env["conversation.inbox.capture.wizard"]
            .with_user(self.user)
            .create(
                {
                    "transport_id": self.transport.id,
                    "external_id": "ext-1",
                    "res_model_id": self.env["ir.model"]._get("res.partner").id,
                    "res_id": self.partner.id,
                }
            )
        )
        self.assertFalse(wizard.res_display_name)

    def test_conversation_match_is_not_a_record_link(self):
        conv = self.env["mail.conversation"].create({"name": "Conv"})
        conv_msg = conv.message_post(body="hello", message_type="comment")
        stub = {
            "in_reply_to": conv_msg.message_id,
            "references": self.msgid,
        }
        self.assertEqual(
            self.transport._resolve_record_from_headers(stub), ("existing", conv)
        )
        action, _fetch = self._open(stub_over=stub)
        self.assertEqual(
            action["context"]["default_mode"], "new"
        )
        self.assertNotIn("default_res_id", action["context"])

    def test_precedence_in_reply_to_wins(self):
        other = self.env["res.partner"].create({"name": "Other Partner"})
        other_msg = other.message_post(body="r")
        stub = {"in_reply_to": other_msg.message_id, "references": self.msgid}
        self.assertEqual(
            self.transport._resolve_record_from_headers(stub), ("link", other)
        )

    def test_off_identical_to_today(self):
        self.transport.record_link_mode = "off"
        action, fetch = self._open()
        self.assertEqual(
            action,
            {
                "type": "ir.actions.act_window",
                "res_model": "conversation.inbox.capture.wizard",
                "views": [[False, "form"]],
                "target": "new",
                "context": {
                    "default_transport_id": self.transport.id,
                    "default_external_id": "ext-1",
                    "default_subject": "Need a quote",
                    "default_mode": "new",
                },
            },
        )
        fetch.assert_not_called()
        form = self._form(action)
        self.assertEqual(form.mode, "new")
        self.assertFalse(form.res_id)

    def test_suggest_presets_and_persists_nothing(self):
        before = self._counts()
        action, _fetch = self._open()
        form = self._form(action)
        self.assertEqual(form.mode, "link")
        self.assertEqual(form.res_model_id.model, "res.partner")
        self.assertEqual(form.res_id, self.partner.id)
        self.assertEqual(form.res_display_name, self.partner.display_name)
        self.assertEqual(self._counts(), before)
        fetch_patch, normalize_patch = self._mock_fetch_normalize(
            in_reply_to=self.msgid
        )
        with fetch_patch, normalize_patch:
            form.save().action_capture()
        links = self.env["mail.conversation.link"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        )
        self.assertEqual(len(links), 1)

    def test_automatic_with_file_in_odoo_files_and_links(self):
        self.transport.write({"record_link_mode": "auto", "default_file_in_odoo": True})
        action, _fetch = self._open()
        self.assertEqual(action["res_model"], "mail.conversation")
        conv = self.env["mail.conversation"].browse(action["res_id"])
        self.assertEqual(
            [(l.res_model, l.res_id, l.reason) for l in conv.link_ids],
            [("res.partner", self.partner.id, "manual")],
        )
        message = self.env["mail.message"].search(
            [("model", "=", "mail.conversation"), ("res_id", "=", conv.id),
             ("external_id", "=", "ext-1")]
        )
        self.assertFalse(message.transport_id)
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_note"))
        before = self._counts()
        again, _fetch = self._open()
        self.assertEqual(again["res_id"], conv.id)
        self.assertEqual(self._counts(), before)

    def test_automatic_archives_once(self):
        self.transport.write(
            {
                "record_link_mode": "auto",
                "default_file_in_odoo": True,
                "archive_on_capture": True,
            }
        )
        with patch.object(
            type(self.env["mail.conversation"]), "_inbox_archive_after_capture"
        ) as archive:
            self._open()
        archive.assert_called_once()

    def test_automatic_without_file_in_odoo_is_suggest(self):
        self.transport.write(
            {"record_link_mode": "auto", "default_file_in_odoo": False}
        )
        before = self._counts()
        action, _fetch = self._open()
        self.assertEqual(action["res_model"], "conversation.inbox.capture.wizard")
        self.assertEqual(action["context"]["default_res_id"], self.partner.id)
        self.assertEqual(self._counts(), before)

    def test_shared_transport_is_off(self):
        self.transport.write(
            {
                "user_id": False,
                "record_link_mode": "auto",
                "default_file_in_odoo": True,
            }
        )
        before = self._counts()
        action, fetch = self._open()
        self.assertEqual(action["res_model"], "conversation.inbox.capture.wizard")
        self.assertNotIn("default_res_id", action["context"])
        fetch.assert_not_called()
        self.assertEqual(self._counts(), before)

    def test_existing_button_keeps_mode(self):
        action, _fetch = self._open(mode="existing")
        form = self._form(action)
        self.assertEqual(form.mode, "existing")
        self.assertEqual(form.res_id, self.partner.id)
