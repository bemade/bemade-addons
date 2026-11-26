"""Use case: the quote of one of our own replies shows the mailbox it was sent
from (real browser, ordinary internal user, option on).

Acceptance criteria:
- AC3 (UI): the reply pop-up opened on our sent reply quotes it from the
  transport's login, not from the user's sending address.

Needs the reply pop-up of conversation_draft; skipped where it is absent.
"""

from unittest.mock import patch

from markupsafe import Markup

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestConversationSenderTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = mail_new_test_user(
            cls.env, login="tour_sender_u", name="Tour Sender", groups="base.group_user"
        )
        cls.env.company.mail_send_from_signature_address = True
        alias = cls.env["mail.alias"].create(
            {
                "alias_name": "ventes-tour",
                "alias_domain_id": cls.env.company.alias_domain_id.id
                or cls.env["mail.alias.domain"].create({"name": "example.com"}).id,
                "alias_model_id": cls.env["ir.model"]._get_id("res.partner"),
            }
        )
        cls.user.mail_send_as_alias_id = alias
        cls.transport = cls.env["conversation.transport"].create(
            {"name": "Boîte du soutien", "sendable": True, "login": "soutien@example.com"}
        )
        cls.conversation = cls.env["mail.conversation"].create(
            {"name": "Demande de prix", "primary_transport_id": cls.transport.id}
        )
        customer = cls.env["res.partner"].create(
            {"name": "Client Dubois", "email": "client@example.com"}
        )
        inbound = cls.conversation.message_post(
            body=Markup("<p>Pouvez-vous nous faire un devis ?</p>"),
            subtype_xmlid="mail.mt_note",
            author_id=customer.id,
        )
        inbound.write(
            {"subject": "Demande de prix", "external_id": "201", "message_id": "<in@client.example>"}
        )
        with patch.object(type(cls.transport), "_send", autospec=True, return_value="out"):
            cls.conversation.with_user(cls.user).action_reply(
                "<p>Votre devis est prêt.</p>", recipients=["client@example.com"]
            )

    def test_quote_shows_the_real_sender(self):
        if "mail.conversation.draft" not in self.env:
            self.skipTest("conversation_draft is not installed")
        self.start_tour(
            "/odoo/action-conversation_base.mail_conversation_action",
            "conversation_sender",
            login=self.user.login,
        )
