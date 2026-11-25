# Seed for the imap_smtp_encryption demo. Run against a throwaway database:
#   odoo-bin shell -d <db> --no-http < imap_smtp_encryption_seed.py
# It creates the administrator's personal mailbox (the flow opens
# /odoo/conversation.transport/<id> of the first transport).
env["conversation.transport"].create(
    {
        "name": "Ma boîte courriel",
        "provider": "imap",
        "user_id": env.ref("base.user_admin").id,
        "login": "moi@example.com",
        "imap_host": "imap.example.com",
        "smtp_host": "smtp.example.com",
    }
)
env.cr.commit()
