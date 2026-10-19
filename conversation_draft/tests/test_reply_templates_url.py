# Acceptance criterion (reply templates, URL access): a user who is not an
# administrator cannot open the "Reply templates" action from its URL, by
# path or by xmlid, nor restore it from a breadcrumb; an administrator gets
# the list of conversation templates.

from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tests.common import JsonRpcException
from odoo.tools.misc import mute_logger

PATH = "reply-templates"
XMLID = "conversation_draft.mail_reply_template_server_action"


@tagged("post_install", "-at_install")
class TestReplyTemplatesUrl(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(
            cls.env, login="reply_tpl_internal", groups="base.group_user"
        )

    def _run(self, action_id):
        return self.make_jsonrpc_request(
            "/web/action/run", {"action_id": action_id}
        )

    def test_non_admin_cannot_open_from_url(self):
        self.authenticate("reply_tpl_internal", "reply_tpl_internal")
        for action_ref in (PATH, XMLID):
            loaded = self.make_jsonrpc_request(
                "/web/action/load", {"action_id": action_ref}
            )
            # The URL only resolves to the server action, which carries no
            # model, domain or views; the web client must run it next.
            self.assertEqual(loaded["type"], "ir.actions.server")
            self.assertNotIn("res_model", loaded)
            self.assertNotIn("domain", loaded)
            with mute_logger("odoo.http"), self.assertRaises(JsonRpcException) as e:
                self._run(loaded["id"])
            self.assertEqual(e.exception.args[0], "odoo.exceptions.AccessError")
        crumbs = self.make_jsonrpc_request(
            "/web/action/load_breadcrumbs", {"actions": [{"action": PATH}]}
        )
        self.assertIn("error", crumbs[0])

    def test_admin_opens_conversation_templates_from_url(self):
        self.authenticate("admin", "admin")
        loaded = self.make_jsonrpc_request("/web/action/load", {"action_id": PATH})
        action = self._run(loaded["id"])
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "mail.template")
        self.assertEqual(action["domain"], [["model", "=", "mail.conversation"]])
        self.assertEqual(
            action["context"]["default_model_id"],
            self.env["ir.model"]._get_id("mail.conversation"),
        )
        crumbs = self.make_jsonrpc_request(
            "/web/action/load_breadcrumbs", {"actions": [{"action": PATH}]}
        )
        self.assertEqual(crumbs, [{"display_name": "Reply templates"}])
