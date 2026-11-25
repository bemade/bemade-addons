# Acceptance criteria (reply templates):
#   * "Reply with template" (conversation) and "Use template" (draft) are
#     offered only while at least one mail.template for conversations
#     exists, evaluated on every read.
#   * A template written for another model does not count.
#   * An administrator-only "Reply templates" menu and action list only the
#     conversation templates; creating one there presets the model.
#   * A user who is not an administrator sees neither the menu nor the action,
#     and cannot run the action (so not open it from its URL either).

from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tools.misc import mute_logger

from .common import DraftCommon


class TestReplyTemplates(DraftCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["mail.template"].search(
            [("model", "=", "mail.conversation")]
        ).unlink()
        cls.draft = cls.env["mail.conversation.draft"].create(
            {"conversation_id": cls.conversation.id}
        )
        cls.conv_model = cls.env["ir.model"]._get_id("mail.conversation")
        cls.action = cls.env.ref(
            "conversation_draft.mail_reply_template_server_action"
        )
        cls.menu = cls.env.ref("conversation_draft.menu_mail_reply_template")

    def _flags(self, user=None):
        conversation = self.conversation.with_user(user) if user else self.conversation
        draft = self.draft.with_user(user) if user else self.draft
        conversation.invalidate_recordset()
        draft.invalidate_recordset()
        return conversation.has_reply_templates, draft.has_reply_templates

    def _window_action(self):
        """The window action the menu opens for an administrator."""
        admin = self.env.ref("base.user_admin")
        return self.action.with_user(admin).run()

    def _template(self, model="mail.conversation"):
        return self.env["mail.template"].create(
            {
                "name": "Reply template",
                "model_id": self.env["ir.model"]._get_id(model),
            }
        )

    def test_buttons_follow_template_existence(self):
        self.assertEqual(self._flags(self.user_a), (False, False))
        template = self._template()
        self.assertEqual(self._flags(self.user_a), (True, True))
        template.unlink()
        self.assertEqual(self._flags(self.user_a), (False, False))

    def test_template_for_another_model_does_not_count(self):
        self._template("res.partner")
        self.assertEqual(self._flags(self.user_a), (False, False))

    def test_forms_carry_the_flag_and_hide_the_buttons(self):
        conv_arch = self.env["mail.conversation"].get_view(view_type="form")["arch"]
        self.assertIn('name="has_reply_templates"', conv_arch)
        self.assertRegex(
            conv_arch,
            r'name="action_open_draft_with_template"[^>]*invisible="not has_reply_templates"',
        )
        draft_arch = self.env["mail.conversation.draft"].get_view(view_type="form")[
            "arch"
        ]
        self.assertIn('name="has_reply_templates"', draft_arch)
        with Form(self.draft.with_user(self.user_a)) as form:
            self.assertFalse(form.has_reply_templates)

    def test_action_lists_only_conversation_templates(self):
        mine = self._template()
        other = self._template("res.partner")
        action = self._window_action()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "mail.template")
        found = self.env["mail.template"].search(action["domain"])
        self.assertIn(mine, found)
        self.assertNotIn(other, found)

    def test_creating_from_the_action_presets_the_model(self):
        action = self._window_action()
        context = action["context"]
        self.assertEqual(context["default_model_id"], self.conv_model)
        form_view = dict((mode, view) for view, mode in action["views"])["form"]
        self.assertEqual(
            form_view,
            self.env.ref("conversation_draft.mail_reply_template_view_form").id,
        )
        with Form(
            self.env["mail.template"].with_context(**context),
            view=form_view,
        ) as form:
            form.name = "Created from the menu"
        created = self.env["mail.template"].search(
            [("name", "=", "Created from the menu")]
        )
        self.assertEqual(created.model, "mail.conversation")
        self.assertEqual(self._flags(self.user_a), (True, True))

    def test_model_is_read_only_in_the_action_form(self):
        view = self.env.ref("conversation_draft.mail_reply_template_view_form")
        arch = self.env["mail.template"].get_view(view.id)["arch"]
        self.assertRegex(arch, r'name="model_id"[^>]*readonly="1"')

    def test_menu_is_admin_only(self):
        admin_group = self.env.ref("base.group_system")
        self.assertEqual(self.menu.action, self.action)
        self.assertEqual(self.menu.group_ids, admin_group)
        self.assertEqual(self.action.group_ids, admin_group)
        Menu = self.env["ir.ui.menu"]
        admin = self.env.ref("base.user_admin")
        self.assertIn(self.menu.id, Menu.with_user(admin)._visible_menu_ids())
        self.assertNotIn(self.menu.id, Menu.with_user(self.user_a)._visible_menu_ids())

    def test_non_admin_cannot_run_the_action(self):
        with mute_logger("odoo.addons.base.models.ir_actions"):
            with self.assertRaises(AccessError):
                self.action.with_user(self.user_a).run()
