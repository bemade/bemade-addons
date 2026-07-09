#
#    Bemade Inc.
#
#    Copyright (C) 2026-July Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License,
#    version 3.
#
#    For full license details, see https://www.gnu.org/licenses/lgpl-3.0.en.html.
#
{
    "name": "NPO Fundraising CRM Vocabulary",
    "version": "19.0.1.0.0",
    "summary": "Relabels the Sales/CRM vocabulary into fundraising terms "
    "(donations, prospects, donors, solicitors) in English and Quebec French.",
    "description": """
NPO Fundraising CRM Vocabulary
==============================

Re-labels the standard Odoo Sales/CRM vocabulary into non-profit fundraising
terms, so the CRM app reads as a development/fundraising pipeline rather than a
sales pipeline. A reusable base for Quebec non-profits.

The relabel is **bilingual**: it changes the English (``en_US``) base language
*and* ships a Quebec French (``fr_CA``) translation, so the pack is useful both
for a French Quebec instance and, unchanged, for an English NPO.

Mapping (English → French):

- Opportunity → Donation / Don
- Lead → Prospect / Prospect
- Salesperson → Solicitor / Solliciteur
- Sales Team → Development Team / Équipe de développement
- Customer → Donor / Donateur
- Expected Revenue → Expected Amount / Montant attendu
- Won / Lost → Secured / Declined — Réalisé / Refusé
- Stages: New → Qualified → Proposition → Won become
  Identification → Qualification → Solicitation → Secured
  (Identification → Qualification → Sollicitation → Réalisé)

Mechanism
---------

Because Odoo 16+ stores translations as per-record JSONB, the visible French
labels come from translations already loaded by ``crm``. Changing the English
source alone does not change the French UI, so this module:

1. overrides the English source (field ``string``/selection labels via
   ``_inherit``; menu/action/stage record names via data; a couple of
   hard-coded search-view strings via view inheritance), and
2. ships an ``fr_CA`` translation loaded on install with ``overwrite=True``
   (``post_init_hook``) so it wins over the terms ``crm`` already translated.
""",
    "category": "Sales/CRM",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "crm",
        "contacts",
    ],
    "data": [
        "data/crm_stage.xml",
        "data/crm_menu.xml",
        "data/crm_action.xml",
        "views/crm_lead_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
}
