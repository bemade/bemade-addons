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
4. A correction line names the field in the **student's** language
   (``student_id.partner_id.lang``), whoever writes it: an en_US parent correcting a
   fr_CA student's past journal or block gets « (Ce qui a marché) »; an en_US student's
   record keeps English. Per record — two students in one write each get their own. No
   student language → the writer's language as before.
5. The 19.0.8.4.2 migration rewrites the English label right after the ``- **date** ``
   prefix of existing corrections to the student's language; the text after it, lines
   already translated and en_US students' records are left alone; a second run changes
   nothing.
"""
import importlib.util
import os
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
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

    def test_correction_label_without_student_lang_uses_the_writer(self):
        """No language on the student: the writer's language, as before."""
        self.partner.lang = False
        today = fields.Date.context_today(self.Day)
        day = self.make_day(today - timedelta(days=1))
        block = self.make_block(day, "Hier", 45, 1, subject_id=self.math.id, went_well="original")
        block.with_context(lang="fr_CA").write({"went_well": "ajouté le lendemain"})
        self.assertEqual(block.went_well, "original")
        self.assertEqual(block.corrections, "- **%s** (Ce qui a marché): ajouté le lendemain" % fields.Date.to_string(today))

    def _second_student(self, lang):
        partner = self.env["res.partner"].create({"name": "Second Test Student", "lang": lang})
        return self.Student.create({"partner_id": partner.id, "birthdate": "2016-01-01"})

    def test_correction_label_in_the_students_language(self):
        """An en_US writer correcting a fr_CA student's past records: French labels; an
        en_US student's record in the same write keeps English."""
        self.partner.lang = "fr_CA"
        other = self._second_student("en_US")
        today = fields.Date.context_today(self.Day)
        today_str = fields.Date.to_string(today)
        past = today - timedelta(days=2)
        day_fr = self.make_day(past)
        day_en = self.Day.create({"student_id": other.id, "date": past})
        Journal = self.env["homeschool.journal"].with_context(lang="en_US")
        fr_entry = Journal.create({"day_id": day_fr.id, "went_well": "original", "indicator_notes": "R3 0"})
        en_entry = Journal.create({"day_id": day_en.id, "went_well": "original"})
        (fr_entry | en_entry).write({"went_well": "rewritten"})
        self.assertEqual(fr_entry.corrections, "- **%s** (Ce qui a marché): rewritten" % today_str)
        self.assertEqual(en_entry.corrections, "- **%s** (What worked): rewritten" % today_str)
        fr_entry.write({"indicator_notes": "R3 1"})
        self.assertTrue(fr_entry.corrections.endswith("- **%s** (Notes d'indicateurs): R3 1" % today_str))
        # blocks: the same rule
        Block = self.Block.with_context(lang="en_US")
        fr_block = Block.create({"day_id": day_fr.id, "name": "Hier", "went_badly": "x"})
        en_block = Block.create({"day_id": day_en.id, "name": "Yesterday", "went_badly": "x"})
        (fr_block | en_block).write({"went_badly": "worse"})
        self.assertEqual(fr_block.corrections, "- **%s** (Ce qui a mal été): worse" % today_str)
        self.assertEqual(en_block.corrections, "- **%s** (What went badly): worse" % today_str)
        # an API-style write without any lang in the context: still the student's language
        fr_block.with_context(lang=None).write({"went_badly": "worst"})
        self.assertTrue(fr_block.corrections.endswith("- **%s** (Ce qui a mal été): worst" % today_str))

    def _migration(self):
        path = os.path.join(get_module_path("homeschool"), "migrations", "19.0.8.4.2", "post-migrate.py")
        spec = importlib.util.spec_from_file_location("homeschool_post_migrate_19_0_8_4_2", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        return migration

    def test_migration_rewrites_english_labels(self):
        migration = self._migration()
        self.partner.lang = "fr_CA"
        other = self._second_student("en_US")
        past = fields.Date.context_today(self.Day) - timedelta(days=9)
        day_fr = self.make_day(past)
        day_en = self.Day.create({"student_id": other.id, "date": past})
        old = "\n".join([
            "- **2026-01-05** (What worked): went fine (What worked) — not a label",
            "- **2026-01-05** (What went badly): the end",
            "- **2026-01-06** (Notes): - a note",
            "- **2026-01-06** (Indicator Notes): R3 1",
            "- **2026-01-07** (Ce qui a marché): already French",
            "(What worked): no date prefix, untouched",
        ])
        Journal = self.env["homeschool.journal"]
        fr_entry = Journal.create({"day_id": day_fr.id, "went_well": "a"})
        en_entry = Journal.create({"day_id": day_en.id, "went_well": "a"})
        fr_block = self.make_block(day_fr, "Hier", 45, 1)
        en_block = self.Block.create({"day_id": day_en.id, "name": "Yesterday"})
        block_old = "- **2026-01-05** (Note): late note\n- **2026-01-05** (What worked): (What went badly) kept"
        (fr_entry | en_entry).write({"corrections": old})
        (fr_block | en_block).write({"corrections": block_old})
        self.env.invalidate_all()
        changed = migration.rewrite_correction_labels(self.env)
        self.assertEqual(changed, 2, "one journal, one block")
        self.assertEqual(fr_entry.corrections, "\n".join([
            "- **2026-01-05** (Ce qui a marché): went fine (What worked) — not a label",
            "- **2026-01-05** (Ce qui a mal été): the end",
            "- **2026-01-06** (Notes): - a note",
            "- **2026-01-06** (Notes d'indicateurs): R3 1",
            "- **2026-01-07** (Ce qui a marché): already French",
            "(What worked): no date prefix, untouched",
        ]))
        self.assertEqual(fr_block.corrections, "- **2026-01-05** (Note): late note\n- **2026-01-05** (Ce qui a marché): (What went badly) kept")
        self.assertEqual(en_entry.corrections, old, "an en_US student's record is left alone")
        self.assertEqual(en_block.corrections, block_old)
        # idempotent
        self.assertEqual(migration.rewrite_correction_labels(self.env), 0)
        migration.migrate(self.env.cr, "19.0.8.4.1")
        self.env.invalidate_all()
        self.assertIn("(Ce qui a marché): went fine", fr_entry.corrections)

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

    def test_close_day_messages(self):
        """« Fermer la journée »: the blank-minutes refusal, the menu's « nothing to close »
        and the « empty » day state, in French."""
        self.assertEqual(dict(self.fr["homeschool.day"]._fields["journal_state"]._description_selection(self.fr))["empty"], "Vide")
        today = fields.Date.context_today(self.Day)
        day = self.make_day(today)
        self.make_block(day, "Segment", 45, 1, subject_id=self.math.id)
        Wizard = self.fr["homeschool.close.day.wizard"]
        wiz = Wizard.create({"day_id": day.id})
        with self.assertRaises(UserError) as cm:
            wiz.action_next()
        self.assertEqual(str(cm.exception), "Inscris les minutes (total et avec un adulte), ou clique « Sauter ce bloc ».")
        day.unlink()
        self.Day.search([("student_id", "=", self.student.id)]).unlink()
        with self.assertRaises(UserError) as cm:
            Wizard.action_open_today()
        self.assertEqual(str(cm.exception), "Rien à fermer : aucune journée incomplète.")
