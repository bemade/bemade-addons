# -*- coding: utf-8 -*-
"""UC-22 — An English grammar practice set (subject ANG).

Acceptance criteria
-------------------
1. A parent action « Load English practice set » (``deck.action_load_english()``, managers
   only) loads the deck « English grammar » with the English subject
   (``homeschool.subject_ang``), from ``data/english_grammar_units.csv`` and
   ``_cards.csv``, through the same loader as the grammar and math decks. Idempotent.
2. Six units in teaching order: irregular plurals, the possessive 's, past tense -ed
   spelling, irregular past verbs, capitals and end marks, one idea per sentence. Each has
   an intro (the rule and examples) and a short hint in English, and about 15 choice cards
   (12 to 16), easiest first, each with 2 to 4 options and exactly one correct, the
   right one not always in the same place.
3. Each unit lists the curriculum items it practises, matched by their code (``ALS-C23-…``)
   when present in the database; codes not found are skipped.
4. Teach first: every unit stays locked until a parent unlocks it (``action_unlock``).
5. The deck is not a daily deck (it joins the quest rotation, UC-23).
6. Synthetic content: names only from Léa, Samuel, Noah, Emma, Zoé, Olivier.
"""
import re

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import PracticeCase

UNITS = ["Irregular plurals", "The possessive 's", "Past tense: -ed spelling", "Irregular past verbs",
         "Capitals and end marks", "One idea per sentence"]
FORBIDDEN = re.compile(r"F[eé]lix|Jos[eé]e|Joss|Denis|Glory", re.I)


@tagged("post_install", "-at_install")
class TestEnglishDeck(PracticeCase):

    def setUp(self):
        super().setUp()
        self.plural_ref = self.Item.create({"code": "ALS-C23-pluriels-3", "name": "Irregular plurals",
                                            "subject_id": self.env.ref("homeschool.subject_ang").id,
                                            "priorite": "core"})
        self.Deck.action_load_english()
        self.english = self.Deck.search([("name", "=", "English grammar")])

    def test_deck_units_and_subject(self):
        self.assertEqual(len(self.english), 1)
        self.assertEqual(self.english.subject_id, self.env.ref("homeschool.subject_ang"))
        self.assertEqual(self.english.unit_ids.sorted("sequence").mapped("name"), UNITS)
        self.assertFalse(self.english.quest_daily)

    def test_cards(self):
        for unit in self.english.unit_ids:
            self.assertTrue(unit.intro, unit.name)
            positions = {item.choice_ids.sorted("sequence").mapped("correct").index(True) for item in unit.item_ids}
            self.assertGreater(len(positions), 1, "the right answer moves around (%s)" % unit.name)
            self.assertTrue(12 <= len(unit.item_ids) <= 16, unit.name)
            for item in unit.item_ids:
                self.assertEqual(item.answer_mode, "choices")
                self.assertTrue(2 <= len(item.choice_ids) <= 4, item.key)
                self.assertEqual(len(item.choice_ids.filtered("correct")), 1, item.key)
                self.assertEqual(item.choice_ids.filtered("correct").label, item.answer)
                self.assertEqual(len(set(item.choice_ids.mapped("label"))), len(item.choice_ids), item.key)
                self.assertTrue(item.hint, item.key)
                for text in [item.prompt, item.hint] + item.choice_ids.mapped("label"):
                    self.assertFalse(FORBIDDEN.search(text), item.key)

    def test_idempotent(self):
        counts = (len(self.english.unit_ids), len(self.english.item_ids))
        self.Deck.action_load_english()
        self.assertEqual(self.Deck.search_count([("name", "=", "English grammar")]), 1)
        self.assertEqual((len(self.english.unit_ids), len(self.english.item_ids)), counts)

    def test_refs(self):
        plurals = self.english.unit_ids.filtered(lambda u: u.name == "Irregular plurals")
        self.assertEqual(plurals.curriculum_item_ids, self.plural_ref)

    def test_locked_until_taught(self):
        unit = self.english.unit_ids.sorted("sequence")[0]
        self.assertFalse(unit._unlocked_for(self.student))
        session = self.Session._start(self.student, self.english, kind="unit", unit=unit)
        self.assertFalse(session._current_item())
        self.english.unit_ids.sorted("sequence")[:3].action_unlock(self.student)
        self.assertEqual(len(self.english.unit_ids._unlocked_for(self.student)), 3)
        session = self.Session._start(self.student, self.english, kind="unit", unit=unit)
        self.assertTrue(session._current_item())

    def test_managers_only(self):
        with self.assertRaises(AccessError):
            self.Deck.with_user(new_test_user(self.env, login="uc22_portal", groups="base.group_portal")
                                ).action_load_english()
