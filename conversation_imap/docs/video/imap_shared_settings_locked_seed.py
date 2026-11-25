# Seed for the imap_shared_settings_locked demo. Run against a throwaway
# database, then record the flow as the user created here (login
# demo_ordinaire, password demo_ordinaire):
#   odoo-bin shell -d <db> --no-http < imap_shared_settings_locked_seed.py
env["res.users"].with_context(no_reset_password=True).create(
    {
        "name": "Utilisateur ordinaire",
        "login": "demo_ordinaire",
        "password": "demo_ordinaire",
        "email": "demo_ordinaire@example.com",
        "group_ids": [(6, 0, [env.ref("base.group_user").id])],
    }
)
env["conversation.transport"].create(
    {
        "name": "Boîte partagée",
        "provider": "imap",
        "login": "equipe@example.com",
        "imap_host": "imap.example.com",
        "smtp_host": "smtp.example.com",
    }
)
env.cr.commit()
