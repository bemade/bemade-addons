# Seed for the conversation_own_address_tour demo. Run against a throwaway
# database:
#   odoo-bin shell -d <db> --no-http < conversation_own_address_tour_seed.py
# It receives a mail addressed to the team's own address and two outside
# people, through the real mail gateway.

domain = env["mail.alias.domain"].search([], limit=1)
if not domain:
    domain = env["mail.alias.domain"].create({"name": "example.com", "bounce_alias": "bounce", "catchall_alias": "catchall"})
model = env["ir.model"]._get("mail.conversation")
alias = env["mail.alias"].create(
    {
        "alias_name": "equipe-soumissions",
        "alias_model_id": model.id,
        "alias_domain_id": domain.id,
    }
)
team_address = "equipe-soumissions@%s" % domain.name
raw = (
    "MIME-Version: 1.0\n"
    "Date: Thu, 27 Dec 2018 16:27:45 +0100\n"
    "Message-ID: <demo-own-address@example.com>\n"
    "Subject: Soumission\n"
    "From: Client Tremblay <client@example.net>\n"
    "To: %s, Marie Roy <marie@example.org>, jean@example.org\n"
    'Content-Type: text/plain; charset="UTF-8"\n\n'
    "Bonjour, pouvez-vous nous envoyer une soumission ?\n"
) % team_address
env["mail.thread"].sudo().message_process(False, raw)
env.cr.commit()
