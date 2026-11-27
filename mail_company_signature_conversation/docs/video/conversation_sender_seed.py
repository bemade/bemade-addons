# Seed for the conversation_sender demo. Run against a throwaway database:
#   odoo-bin shell -d <db> --no-http < conversation_sender_seed.py
# The option « Send from the signature address » is on, the user's sending
# address is a team alias, and the reply went out over another team's mailbox
# (the reply is written by the user, not by the shell's superuser; the
# transport's send is mocked: a demo database has no mail server).
from unittest.mock import patch

from markupsafe import Markup

company = env.company
domain = company.alias_domain_id or env["mail.alias.domain"].create({"name": "example.com"})
company.mail_send_from_signature_address = True
alias = env["mail.alias"].create(
    {
        "alias_name": "ventes",
        "alias_domain_id": domain.id,
        "alias_model_id": env["ir.model"]._get_id("res.partner"),
    }
)
user = env.ref("base.user_admin")
user.mail_send_as_alias_id = alias

transport = env["conversation.transport"].create(
    {"name": "Boîte du soutien", "sendable": True, "login": "soutien@example.com"}
)
conversation = env["mail.conversation"].create(
    {"name": "Demande de prix", "primary_transport_id": transport.id}
)
customer = env["res.partner"].create(
    {"name": "Client Dubois", "email": "client@example.com"}
)
received = conversation.message_post(
    body=Markup("<p>Pouvez-vous nous faire un devis ?</p>"),
    subtype_xmlid="mail.mt_note",
    author_id=customer.id,
)
received.write(
    {"subject": "Demande de prix", "external_id": "201", "message_id": "<demo-in@client.example>"}
)
with patch.object(type(transport), "_send", return_value="demo-out", autospec=True):
    conversation.with_user(user).action_reply(
        "<p>Votre devis est prêt.</p>", recipients=["client@example.com"]
    )
env.cr.commit()
