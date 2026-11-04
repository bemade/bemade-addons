# Copyright 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
{
    "name": "Hermes — boutons d'approbation",
    "summary": "Boutons cliquables pour approuver/refuser les commandes "
               "d'Hermes dans Discuss",
    "version": "19.0.1.0.1",
    "author": "Bemade",
    "website": "https://bemade.org",
    "license": "AGPL-3",
    "category": "Productivity/Discuss",
    "depends": ["mail"],
    "assets": {
        # Chargé dans le client backend (où vit Discuss) : intercepte le clic
        # des boutons d'approbation pour un envoi fetch, sans recharger la page.
        "web.assets_backend": [
            "hermes_boutons/static/src/hermes_url.js",
            "hermes_boutons/static/src/hermes_boutons.js",
        ],
        "web.assets_unit_tests": [
            "hermes_boutons/static/tests/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
