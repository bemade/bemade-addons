# -*- coding: utf-8 -*-
"""UC-16 — French (fr_CA) for the whole module.

Acceptance criteria
-------------------
1. ``i18n/fr_CA.po`` carries the module's terms: with ``fr_CA`` active and the terms
   loaded, an fr_CA environment gets French field labels, selection values and python
   messages (``_description_string`` / ``_description_selection`` / an ``AccessError``).
2. A day's ``display_name`` shows the weekday in the user's language (« lun. 2 mars »
   in fr_CA, « Mon 2 Mar » in en_US); its stored ``name`` keeps the English weekday.
3. English is untouched for an en_US environment.
"""
from datetime import date

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestI18n(HomeschoolCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_CA")
        cls.env["ir.module.module"]._load_module_terms(["homeschool"], ["fr_CA"])
        cls.fr = cls.env(context=dict(cls.env.context, lang="fr_CA"))

    def test_field_label_and_selection(self):
        Trace = self.fr["homeschool.trace"]
        self.assertEqual(Trace._fields["name"]._description_string(self.fr), "Titre")
        self.assertEqual(Trace._fields["student_comment"]._description_string(self.fr), "Dans les mots de l'élève")
        self.assertEqual(dict(Trace._fields["diffusion"]._description_selection(self.fr))["institutional"], "Institutionnelle")
        Block = self.fr["homeschool.block"]
        self.assertEqual(dict(Block._fields["kind"]._description_selection(self.fr))["reading"], "Lecture")
        self.assertEqual(dict(Block._fields["kind"]._description_selection(self.fr))["ressource"], "Ressource")
        self.assertEqual(self.fr["homeschool.day"]._fields["is_off"]._description_string(self.fr), "Journée sans école")
        for model in ("homeschool.block", "homeschool.deliverable", "homeschool.block.template"):
            self.assertEqual(self.fr[model]._fields["plan_key"]._description_string(self.fr), "Clé du plan")
        self.assertEqual(self.fr.ref("homeschool.action_report_day_list").name, "Ma liste du jour")
        self.assertEqual(self.env.ref("homeschool.action_report_day_list").name, "Day's list")
        Wizard = self.fr["homeschool.close.day.wizard"]
        self.assertEqual(Wizard._fields["minutes_total"]._description_string(self.fr), "Réel (min)")
        self.assertEqual(Wizard._fields["minutes_adult_present"]._description_string(self.fr), "Adulte présent (min)")
        self.assertEqual(Wizard._fields["adult_missing_names"]._description_string(self.fr), "Blocs sans minutes adulte")
        self.assertEqual(dict(Wizard._fields["status"]._description_selection(self.fr))["skipped"], "Sauté")
        self.assertEqual(Wizard._fields["block_intention_html"]._description_string(self.fr), "Intention")
        self.assertEqual(Wizard._fields["block_success_html"]._description_string(self.fr), "Critères de réussite")
        self.assertEqual(self.fr.ref("homeschool.menu_close_day").name, "Fermer la journée")
        self.assertEqual(self.fr.ref("homeschool.action_close_day_wizard").name, "Fermer la journée")
        # english untouched
        self.assertEqual(self.Trace._fields["name"]._description_string(self.env), "Title")
        self.assertEqual(dict(self.Block._fields["kind"]._description_selection(self.env))["reading"], "Reading")

    def test_correction_label_in_the_users_language(self):
        """A correction line names the field in the writer's language."""
        from datetime import timedelta
        today = fields.Date.context_today(self.Day)
        day = self.make_day(today - timedelta(days=1))
        block = self.make_block(day, "Hier", 45, 1, subject_id=self.math.id, went_well="original")
        block.with_context(lang="fr_CA").write({"went_well": "ajouté le lendemain"})
        self.assertEqual(block.went_well, "original")
        self.assertEqual(block.corrections, "- **%s** (Ce qui a marché): ajouté le lendemain" % fields.Date.to_string(today))

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_python_message(self):
        portal = self.portal_user()
        portal.lang = "fr_CA"
        self.student.user_id = portal
        trace = self.Trace.with_user(portal).create({"name": "Mine", "student_id": self.student.id})
        with self.assertRaises(AccessError) as cm:
            trace.with_user(portal).with_context(lang="fr_CA").action_validate()
        self.assertEqual(str(cm.exception), "Seul le parent gestionnaire peut valider une trace.")
        with self.assertRaises(AccessError) as cm:
            trace.with_user(portal).with_context(lang="fr_CA").write({"validated": True})
        self.assertIn("Seul le parent peut modifier validated sur une trace", str(cm.exception))
        with self.assertRaises(AccessError) as cm:
            trace.with_user(portal).action_validate()
        self.assertEqual(str(cm.exception), "Only a homeschool manager can validate a trace.")

    def test_day_display_name(self):
        day = self.make_day(date(2026, 3, 2))
        self.assertEqual(day.name, "Mon 2026-03-02")
        self.assertEqual(day.with_context(lang="en_US").display_name, "Mon 2 Mar")
        self.assertEqual(day.with_context(lang="fr_CA").display_name, "lun. 2 mars")
        self.assertEqual(self.fr["homeschool.day"].browse(day.id).display_name, "lun. 2 mars")
