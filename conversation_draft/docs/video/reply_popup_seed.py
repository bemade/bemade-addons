# Seed for the reply_popup demo. Run against a throwaway database:
#   odoo-bin shell -d <db> --no-http < reply_popup_seed.py
# It creates a conversation holding a received email, answered from a shared
# mailbox whose SMTP side points at a local sink listening on SMTP_SINK_PORT
# (default 2525), so the Send step really sends.
import os

from markupsafe import Markup

transport = env["conversation.transport"].create(
    {
        "name": "Boîte partagée",
        "provider": "imap",
        "sendable": True,
        "login": "support@example.com",
        "password": "demo",
        "smtp_host": "127.0.0.1",
        "smtp_ssl": False,
        "smtp_port": int(os.environ.get("SMTP_SINK_PORT", "2525")),
    }
)
conversation = env["mail.conversation"].create(
    {"name": "Retard de livraison", "primary_transport_id": transport.id}
)
env["mail.conversation.participant"].create(
    {
        "conversation_id": conversation.id,
        "email": "client@example.com",
        "role": "requester",
    }
)
customer = env["res.partner"].create(
    {"name": "Client Dubois", "email": "client@example.com"}
)
received = conversation.message_post(
    body=Markup("<p>Quand ma commande arrive-t-elle ?</p>"),
    subtype_xmlid="mail.mt_note",
    author_id=customer.id,
)
received.write({"subject": "Retard de livraison", "external_id": "101", "message_id": "<demo-inbound@client.example>"})
env.cr.commit()
