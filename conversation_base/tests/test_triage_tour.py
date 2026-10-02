# Acceptance criteria (task #4332, slice 04b, AC21): a browser tour drives
# the triage list (row content, Mark read, Hide/Unhide, Done/Reopen,
# Snooze, Assign, a bulk Done on a subset, opening a row), and the
# server-side state it leaves behind matches.

from odoo import Command, fields
from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged

NAMES = ("Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta")


@tagged("post_install", "-at_install")
class TestConversationTriageTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_triage_u", name="Tour User", groups="base.group_user"
        )
        cls.colleague = mail_new_test_user(
            cls.env,
            login="tour_triage_b",
            name="Tour Colleague",
            groups="base.group_user",
        )
        team = cls.env["mail.conversation.team"].create(
            {
                "name": "Tour Team",
                "member_ids": [Command.set([cls.user.id, cls.colleague.id])],
            }
        )
        customer = cls.env["res.partner"].create(
            {"name": "Tour Customer", "email": "tour.customer@example.com"}
        )
        linked = cls.env["res.partner"].create({"name": "Tour Linked Co"})
        cls.convs = {}
        for name in NAMES:
            conv = (
                cls.env["mail.conversation"]
                .with_context(mail_create_nosubscribe=True, mail_create_nolog=True)
                .create({"name": "%s conversation" % name, "team_id": team.id})
            )
            conv.message_post(
                body="<p>Snippet for %s</p>" % name,
                author_id=customer.id,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )
            cls.convs[name] = conv
        cls.env["mail.conversation.link"].create(
            {
                "conversation_id": cls.convs["Alpha"].id,
                "res_model": "res.partner",
                "res_id": linked.id,
            }
        )

    def _member(self, conv, user):
        return self.env["mail.conversation.member"].search(
            [("conversation_id", "=", conv.id), ("user_id", "=", user.id)]
        )

    def test_triage_tour(self):
        for conv in self.convs.values():
            self.assertTrue(self._member(conv, self.user).unread)
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_triage_tour",
            login=self.user.login,
        )
        self.env.invalidate_all()
        alpha = self._member(self.convs["Alpha"], self.user)
        self.assertFalse(alpha.is_handled)
        self.assertFalse(alpha.unread)
        gamma = self._member(self.convs["Gamma"], self.user)
        self.assertTrue(gamma.is_handled)
        self.assertGreater(gamma.snooze_until, fields.Datetime.now())
        for name in ("Beta", "Delta", "Eta"):
            self.assertEqual(self.convs[name].state, "open", name)
        for name in ("Epsilon", "Zeta"):
            self.assertEqual(self.convs[name].state, "done", name)
        self.assertEqual(self.convs["Delta"].user_id, self.colleague)
        for conv in self.convs.values():
            other = self._member(conv, self.colleague)
            self.assertTrue(other.unread)
            self.assertFalse(other.is_handled)
