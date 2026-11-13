# -*- coding: utf-8 -*-
"""UC-18 — Grammar decks for grades 5 and 6 (Québec PDA, French).

Acceptance criteria
-------------------
1. The same parent action as UC-15 (« Load French grammar decks ») also loads four decks
   covering the grammar knowledge the PDA marks as learnt in 5e–6e (I or A): « Classes de
   mots », « Accords », « Conjugaison » and « Syntaxe et ponctuation », one unit per
   competency, in teaching order, with subject French.
2. Each unit has an intro (the rule with an example), a hint and 12 to 16 choice cards,
   each with exactly one correct option, easier cards first. French typography: prompts and
   options keep « », ? ! : on the same line as their word (non-breaking spaces).
3. Each unit lists the curriculum items it practises (``curriculum_item_ids``), matched by
   their PDA code when the curriculum is loaded in the database (codes not found are
   skipped). Loading again links what was missing and creates no duplicates.
4. Like every concept unit, they stay locked until a parent unlocks them (teach first).
5. Synthetic content: no learner's name in any card.
"""
from odoo.tests import tagged

from .common import PracticeCase

UNITS = {
    "Classes de mots": [
        "Les sortes de déterminants", "Les pronoms", "L'adverbe", "Former un adverbe en « -ment »",
        "La préposition", "La conjonction"],
    "Accords": [
        "Le verbe et son sujet pronom", "Le verbe et son sujet groupe du nom", "Des sujets coordonnés",
        "Le participe passé avec « être »", "L'adjectif attribut du sujet", "Plusieurs noms, noms de peuples"],
    "Conjugaison": [
        "Infinitif ou verbe conjugué", "Les verbes en « -cer » et « -ger »", "Les verbes qui changent leur radical",
        "Prendre, mettre, tenir, venir, rendre", "L'impératif présent", "Le subjonctif présent",
        "Le passé composé", "« avoir » ou « être » ?", "Les autres temps composés"],
    "Syntaxe et ponctuation": [
        "Sujet, prédicat, complément de phrase", "Le complément de phrase", "Les types de phrases",
        "La phrase interrogative", "La phrase négative", "La virgule", "Deux-points et guillemets",
        "Le groupe du nom et ses expansions", "Le groupe du verbe", "Attribut, complément direct ou indirect"],
}


@tagged("post_install", "-at_install")
class TestGrammar56(PracticeCase):

    def load(self):
        self.Deck.action_load_grammar_fr()
        return self.Deck.search([("name", "in", list(UNITS))])

    def test_decks_and_units(self):
        decks = self.load()
        self.assertEqual(sorted(decks.mapped("name")), sorted(UNITS))
        for deck in decks:
            self.assertEqual(deck.subject_id, self.fle)
            self.assertEqual(deck.unit_ids.sorted("sequence").mapped("name"), UNITS[deck.name])

    def test_cards(self):
        for unit in self.load().unit_ids:
            self.assertTrue(unit.intro, unit.name)
            self.assertTrue(12 <= len(unit.item_ids) <= 16, unit.name)
            for item in unit.item_ids:
                self.assertEqual(item.answer_mode, "choices")
                self.assertEqual(len(item.choice_ids.filtered("correct")), 1, item.key)
                self.assertEqual(item.answer, item.choice_ids.filtered("correct").label)
                self.assertTrue(item.hint, item.key)
                for text in [item.prompt] + item.choice_ids.mapped("label"):
                    for bad in ("« ", " »", " ?", " !", " :"):
                        self.assertNotIn(bad, text, item.key)

    def test_curriculum_links(self):
        cp = self.env["homeschool.item"].create({
            "code": "FLE-E-SYN-C-E.4.a.i", "name": "effacement", "subject_id": self.fle.id})
        decks = self.load()
        unit = decks.unit_ids.filtered(lambda u: u.name == "Le complément de phrase")
        self.assertEqual(unit.curriculum_item_ids, cp)
        # an item loaded later is linked on the next load, without duplicates
        moved = self.env["homeschool.item"].create({
            "code": "FLE-E-SYN-C-E.4.a.ii", "name": "déplacement", "subject_id": self.fle.id})
        counts = (len(decks.unit_ids), len(decks.item_ids))
        decks = self.load()
        self.assertEqual(unit.curriculum_item_ids, cp | moved)
        self.assertEqual((len(decks.unit_ids), len(decks.item_ids)), counts)

    def test_locked_until_unlocked(self):
        units = self.load().unit_ids
        self.assertFalse(units._unlocked_for(self.student))

    def test_synthetic(self):
        texts = " ".join(self.load().item_ids.mapped(lambda i: "%s %s" % (i.prompt, i.hint)))
        for name in ("Felix", "Félix", "Josée"):
            self.assertNotIn(name, texts)
