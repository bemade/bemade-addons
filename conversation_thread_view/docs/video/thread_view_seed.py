# Seed for the thread_view demo. Run against a throwaway database:
#   odoo-bin shell -d <db> --no-http < thread_view_seed.py
# It creates a conversation holding a received email and an internal note,
# answered from a shared mailbox whose SMTP side points at a local sink
# listening on SMTP_SINK_PORT (default 2525), so the Send step really sends.
import os
from datetime import timedelta

from markupsafe import Markup

from odoo import Command, fields

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
team = env["mail.conversation.team"].create({"name": "Expédition"})
tag = env["mail.conversation.tag"].create({"name": "Urgent"})
conversation = env["mail.conversation"].create(
    {
        "name": "Retard de livraison",
        "primary_transport_id": transport.id,
        "user_id": env.ref("base.user_admin").id,
        "team_id": team.id,
        "tag_ids": [Command.set(tag.ids)],
    }
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
now = fields.Datetime.now()
conversation.message_ids.write({"date": now - timedelta(days=3)})
received = conversation.message_post(
    body=Markup("<p>Quand ma commande arrive-t-elle ?</p>"),
    message_type="email",
    subtype_xmlid="mail.mt_note",
    author_id=customer.id,
)
received.write(
    {
        "subject": "Retard de livraison",
        "external_id": "101",
        "message_id": "<demo-inbound@client.example>",
        "date": now - timedelta(days=2),
    }
)
note = conversation.message_post(
    body=Markup("<p>Note interne : vérifier avec l'entrepôt.</p>"),
    message_type="comment",
    subtype_xmlid="mail.mt_note",
)
note.write({"date": now - timedelta(days=1)})
env.cr.commit()
