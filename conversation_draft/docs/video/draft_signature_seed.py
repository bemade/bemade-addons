# Seed for the draft_signature demo. Run against a throwaway database:
#   odoo-bin shell -d <db> --no-http < draft_signature_seed.py
# It gives the demo user a signature and creates a conversation answered from a
# shared mailbox (no team inbox) whose SMTP side points at a local sink
# listening on SMTP_SINK_PORT (default 2525), so the Send step really sends.
import os

env["res.users"].browse(2).signature = "<p>Cordialement,<br/>Administrateur</p>"
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
    {"name": "Question de livraison", "primary_transport_id": transport.id}
)
env["mail.conversation.participant"].create(
    {
        "conversation_id": conversation.id,
        "email": "client@example.com",
        "role": "requester",
    }
)
env.cr.commit()
