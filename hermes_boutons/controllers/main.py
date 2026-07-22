# Copyright 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Le contrôleur derrière les boutons d'approbation d'Hermes.

POURQUOI IL EXISTE. Quand Hermes demande une approbation dans Discuss
(« Reply /approve to execute… »), l'adaptateur remplace l'invite par des
boutons. Chaque bouton pointe ici. Ce contrôleur poste la commande dans le
canal — AU NOM DE L'UTILISATEUR QUI CLIQUE.

C'EST LE POINT DE SÉCURITÉ, et il mérite d'être dit en entier : une
approbation n'est pas un texte, c'est une identité. En postant comme
l'utilisateur de la session (auth="user"), le message arrive signé par un
humain, et la garde d'auteur du gateway d'Hermes le valide exactement comme
un message tapé. Si quelqu'un HORS du groupe autorisé clique, son message
est posté puis IGNORÉ par la garde — le comportement déjà en place. Ce
contrôleur n'accorde donc aucun pouvoir : il économise la frappe, rien
d'autre.

LISTE BLANCHE STRICTE des commandes. Sans elle, ce contrôleur serait une
fabrique de faux messages : n'importe quel lien pourrait faire poster
n'importe quoi à n'importe qui. Avec elle, le pire qu'un lien forgé puisse
faire est d'approuver une commande QU'HERMES A LUI-MÊME DEMANDÉE — et
seulement si le cliqueur est du groupe autorisé.

LIMITE ASSUMÉE (v1) : c'est un GET qui écrit, donc pas de jeton CSRF. Un
lien forgé sur un autre site pourrait déclencher un clic involontaire. Le
périmètre réel de l'abus est étroit (liste blanche + garde d'auteur +
approbation seulement s'il y a une commande en attente), et l'instance n'est
pas publique. À durcir en POST+confirmation si le canal s'ouvre un jour à
un public plus large.
"""
from werkzeug.utils import redirect

from odoo import http
from odoo.http import request

# Préfixes de commande possibles du framework (typed_command_prefix). On
# accepte /, ! et . — la commande complète doit rester dans cette liste.
_COMMANDES = set()
for _p in ("/", "!", "."):
    _COMMANDES |= {_p + "approve", _p + "approve session",
                   _p + "approve always", _p + "deny"}


class HermesBoutons(http.Controller):

    @http.route("/hermes/repondre", type="http", auth="user",
                methods=["GET"], csrf=False)
    def repondre(self, canal=None, cmd=None, **kwargs):
        # 1. La commande DOIT être de la liste blanche — voir le module doc.
        if cmd not in _COMMANDES:
            return request.not_found()
        # 2. Le canal doit exister et être accessible à l'utilisateur. On
        #    passe par l'env de la session (pas de sudo) : les règles
        #    d'accès d'Odoo s'appliquent telles quelles.
        try:
            canal_id = int(canal)
        except (TypeError, ValueError):
            return request.not_found()
        channel = request.env["discuss.channel"].browse(canal_id).exists()
        if not channel:
            return request.not_found()
        # 3. Poster COMME L'UTILISATEUR. Aucun sudo nulle part : si l'accès
        #    au canal lui est refusé, l'exception d'Odoo fait foi.
        channel.message_post(
            body=cmd,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        # 4. Deux appelants possibles :
        #    - le JS (asset du module) fait un fetch et pose l'en-tête
        #      X-Hermes-Ajax : on rend un 204 vide, la page ne bouge pas, le
        #      message apparait par le bus normal de Discuss.
        #    - un clic SANS JS (repli) navigue vers cette route : on redirige
        #      vers le fil. Le lien reste donc fonctionnel meme JS desactive —
        #      la mise en forme ne retire jamais un moyen d'agir.
        if request.httprequest.headers.get("X-Hermes-Ajax"):
            return request.make_response("", status=204)
        return redirect("/odoo/discuss")
