# Acceptance criteria: a browser tour, run as an ordinary internal user (not
# an administrator), opens a record with linked conversations, sees the tab
# with the right count, opens a conversation from it; the opened conversation
# (itself the target of a link from another conversation) shows no tab; a
# record without link shows no tab. The server state it leaves behind: nothing was posted on the
# record.
#
# The tours run on the test's own res.partner list/form views and action, not
# on the stock partner action: when other addons are installed in the same
# database, they can add fields the ordinary user may not read to the stock
# partner form, which then fails to load. A primary view created here has no
# inheriting views, so the record opens whatever else is installed, and it
# still carries the standard chatter widget the tab is built on.

from datetime import timedelta

from odoo import Command, fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestRecordTabTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="rec_tab_tour", name="Tour User", groups="base.group_user"
        )
        cls.record = cls.env["res.partner"].create({"name": "Industries Tremblay"})
        cls.unlinked_record = cls.env["res.partner"].create({"name": "Client Sans Lien"})
        View = cls.env["ir.ui.view"]
        list_view = View.create(
            {
                "name": "Relevant conversations tour list",
                "model": "res.partner",
                "type": "list",
                "mode": "primary",
                "arch": '<list><field name="name"/></list>',
            }
        )
        form_view = View.create(
            {
                "name": "Relevant conversations tour form",
                "model": "res.partner",
                "type": "form",
                "mode": "primary",
                "arch": '<form><sheet><field name="name"/></sheet><chatter/></form>',
            }
        )
        cls.action = cls.env["ir.actions.act_window"].create(
            {
                "name": "Relevant conversations tour",
                "res_model": "res.partner",
                "view_mode": "list,form",
                "domain": str([("id", "in", (cls.record | cls.unlinked_record).ids)]),
                "view_ids": [
                    Command.create({"sequence": 1, "view_mode": "list", "view_id": list_view.id}),
                    Command.create({"sequence": 2, "view_mode": "form", "view_id": form_view.id}),
                ],
            }
        )
        cls.start_url = f"/odoo/action-{cls.action.id}"
        Conversation = cls.env["mail.conversation"].with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True
        )
        conversations = Conversation
        for hours, name, state in (
            (1, "Retard de livraison", "open"),
            (5, "Soumission Q-1042 - précisions", "done"),
        ):
            conversation = Conversation.create(
                {"name": name, "state": state, "user_id": cls.user.id}
            )
            conversation.message_post(
                body="Bonjour",
                date=fields.Datetime.now() - timedelta(hours=hours),
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            cls.env["mail.conversation.link"].create(
                {
                    "conversation_id": conversation.id,
                    "res_model": "res.partner",
                    "res_id": cls.record.id,
                    "reason": "manual",
                }
            )
            conversations |= conversation
        # The conversation the tour opens is itself linked from another one:
        # its chatter must still show no tab.
        opened, other = conversations
        cls.env["mail.conversation.link"].create(
            {
                "conversation_id": other.id,
                "res_model": "mail.conversation",
                "res_id": opened.id,
            }
        )

    def _record_messages(self):
        return self.env["mail.message"].search_count(
            [("model", "=", "res.partner"), ("res_id", "=", self.record.id)]
        )

    def test_record_tab_tour(self):
        before = self._record_messages()
        self.start_tour(
            self.start_url,
            "conversation_record_tab",
            login=self.user.login,
        )
        self.env.invalidate_all()
        self.assertEqual(self._record_messages(), before)

    def test_record_without_link_tour(self):
        self.start_tour(
            self.start_url,
            "conversation_record_tab_empty",
            login=self.user.login,
        )
