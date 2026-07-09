# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Acceptance criteria for the NPO fundraising vocabulary pack.

The module must relabel the Sales/CRM vocabulary in BOTH languages:

1. English (``en_US`` base) — the field ``string`` labels, the Lead/Opportunity
   and Won/Lost selection labels, and the menu / stage record names must read
   as fundraising terms (Donation, Solicitor, Development Team, Donor, Secured,
   Solicitation, Donors, Fundraising…). This is the reusable base and must hold
   with no language installed.

2. Quebec French (``fr_CA``) — after the fr_CA translation is loaded with
   overwrite=True (as the post_init_hook does on the live instance), the same
   surfaces must read as Don / Solliciteur / Équipe de développement / Donateur
   / Réalisé / Sollicitation / Donateurs / Développement philanthropique,
   overriding crm's own French terms. This is the load-bearing risk (default
   translation load is overwrite=False and would silently skip already-French
   terms), so it is asserted directly.

The "Secured" stage must keep is_won=True so won donations stay classified.
"""
from odoo.tests import TransactionCase, tagged

_FIELDS = [
    "name",
    "user_id",
    "team_id",
    "expected_revenue",
    "partner_id",
    "lost_reason_id",
    "type",
    "won_status",
]


@tagged("post_install", "-at_install")
class TestNpoVocabulary(TransactionCase):
    def _labels(self, lang):
        return self.env["crm.lead"].with_context(lang=lang).fields_get(_FIELDS)

    def test_english_source_relabelled(self):
        f = self._labels("en_US")
        self.assertEqual(f["name"]["string"], "Donation")
        self.assertEqual(f["user_id"]["string"], "Solicitor")
        self.assertEqual(f["team_id"]["string"], "Development Team")
        self.assertEqual(f["expected_revenue"]["string"], "Expected Amount")
        self.assertEqual(f["partner_id"]["string"], "Donor")
        self.assertEqual(f["lost_reason_id"]["string"], "Decline Reason")

        type_sel = dict(f["type"]["selection"])
        self.assertEqual(type_sel["opportunity"], "Donation")
        self.assertEqual(type_sel["lead"], "Prospect")
        won_sel = dict(f["won_status"]["selection"])
        self.assertEqual(won_sel["won"], "Secured")
        self.assertEqual(won_sel["lost"], "Declined")

        # crm.team field label
        team_fields = self.env["crm.team"].with_context(lang="en_US").fields_get(["name"])
        self.assertEqual(team_fields["name"]["string"], "Development Team")

        # Stage / menu record names (English source).
        self.assertEqual(
            self.env.ref("crm.stage_lead3").with_context(lang="en_US").name,
            "Solicitation",
        )
        secured = self.env.ref("crm.stage_lead4").with_context(lang="en_US")
        self.assertEqual(secured.name, "Secured")
        self.assertTrue(secured.is_won)  # still a won stage
        self.assertEqual(
            self.env.ref("crm.res_partner_menu_customer").with_context(lang="en_US").name,
            "Donors",
        )
        self.assertEqual(
            self.env.ref("crm.crm_menu_root").with_context(lang="en_US").name,
            "Fundraising",
        )

    def test_french_translation_relabelled(self):
        # Reproduce what the live (French) instance does: activate fr_CA and
        # load this module's fr_CA.po with overwrite=True.
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env.ref("base.module_npo_fundraising_crm")._update_translations(
            overwrite=True
        )
        self.env.registry.clear_cache()

        f = self._labels("fr_CA")
        self.assertEqual(f["name"]["string"], "Don")
        self.assertEqual(f["user_id"]["string"], "Solliciteur")
        self.assertEqual(f["team_id"]["string"], "Équipe de développement")
        self.assertEqual(f["expected_revenue"]["string"], "Montant attendu")
        self.assertEqual(f["partner_id"]["string"], "Donateur")
        self.assertEqual(f["lost_reason_id"]["string"], "Motif de refus")

        type_sel = dict(f["type"]["selection"])
        self.assertEqual(type_sel["opportunity"], "Don")
        won_sel = dict(f["won_status"]["selection"])
        self.assertEqual(won_sel["won"], "Réalisé")
        self.assertEqual(won_sel["lost"], "Refusé")

        self.assertEqual(
            self.env.ref("crm.stage_lead3").with_context(lang="fr_CA").name,
            "Sollicitation",
        )
        self.assertEqual(
            self.env.ref("crm.stage_lead4").with_context(lang="fr_CA").name,
            "Réalisé",
        )
        self.assertEqual(
            self.env.ref("crm.res_partner_menu_customer").with_context(lang="fr_CA").name,
            "Donateurs",
        )
        self.assertEqual(
            self.env.ref("crm.crm_menu_root").with_context(lang="fr_CA").name,
            "Développement philanthropique",
        )
