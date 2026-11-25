# Seed for the conversation_delivery_icon_tour demo. Run against a throwaway
# database:
#   odoo-bin shell -d <db> --no-http < conversation_delivery_icon_tour_seed.py
# It creates a conversation holding a reply that was sent, followed by a
# colleague, so the reply carries an in-app notification.
from markupsafe import Markup

colleague = env["res.users"].with_context(no_reset_password=True).create(
    {
        "name": "Collègue Tremblay",
        "login": "colleague_demo",
        "email": "colleague@example.com",
        "group_ids": [(6, 0, [env.ref("base.group_user").id])],
    }
)
conversation = env["mail.conversation"].with_context(
    mail_create_nosubscribe=True, mail_create_nolog=True
).create({"name": "Livraison de commande"})
conversation.message_subscribe(partner_ids=colleague.partner_id.ids)
conversation.message_post(
    body=Markup("<p>Votre commande part demain</p>"),
    subtype_xmlid="mail.mt_comment",
    author_id=env.ref("base.partner_admin").id,
)
env.cr.commit()
