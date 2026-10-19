# Acceptance criteria: a browser tour, run as an ordinary internal user (not
# an administrator), opens a record with linked conversations, sees the tab
# with the right count, opens a conversation from it; a record without link
# shows no tab. The server state it leaves behind: nothing was posted on the
# record.

from datetime import timedelta

from odoo import fields
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
        cls.env["res.partner"].create({"name": "Client Sans Lien"})
        Conversation = cls.env["mail.conversation"].with_context(
            mail_create_nosubscribe=True, mail_create_nolog=True
        )
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

    def _record_messages(self):
        return self.env["mail.message"].search_count(
            [("model", "=", "res.partner"), ("res_id", "=", self.record.id)]
        )

    def test_record_tab_tour(self):
        before = self._record_messages()
        self.start_tour(
            "/odoo/action-base.action_partner_form",
            "conversation_record_tab",
            login=self.user.login,
        )
        self.env.invalidate_all()
        self.assertEqual(self._record_messages(), before)

    def test_record_without_link_tour(self):
        self.start_tour(
            "/odoo/action-base.action_partner_form",
            "conversation_record_tab_empty",
            login=self.user.login,
        )
