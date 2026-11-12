# -*- coding: utf-8 -*-
"""UC-01 — Decks, units and items: what can be practiced.

Acceptance criteria
-------------------
1. ``homeschool.practice.deck`` (a subject area, e.g. « Tables de multiplication »,
   « Infinitif ou participe passé »): ``name`` (required, translatable),
   ``company_id``, ``unit_ids``, ``curriculum_item_ids`` (``homeschool.item``),
   ``session_size`` (items per session, default 10, > 0), ``active``.
2. ``homeschool.practice.unit`` (what a parent unlocks: one times table, one grammar
   concept): ``deck_id`` (required, cascade), ``name``, ``sequence``, ``intro`` (the
   worked example shown the first time the unit is served), ``item_ids``,
   ``curriculum_item_ids``.
3. ``homeschool.practice.item``: ``unit_id`` (required, cascade), ``deck_id`` (related),
   ``key`` (stable id, e.g. ``7x8``; **unique per deck**), ``step`` (progression order
   inside the unit: smaller multipliers first), ``prompt``, ``answer`` (text),
   ``answer_mode`` (``keypad`` | ``choices``, required), ``choice_ids`` (ordered),
   ``hint`` (the strategy shown after a miss), ``calibration`` (needs no recall, e.g.
   × 0, × 1, × 10 — used for the learner's timing baseline, UC-05), ``active``.
4. A ``keypad`` answer is digits only; a ``choices`` item has at least two choices and
   exactly one correct (ValidationError otherwise).
5. **Times-tables generator**: ``deck._generate_multiplication(tables=range(0, 13),
   upto=12)`` creates one unit per table and one keypad item per fact ``a × b``
   (``key`` ``a x b``, ``step`` ordered by multiplier, small first, prompt « a × b »,
   answer the product, a derivation hint from a neighbouring fact; × 0, × 1, × 10
   flagged ``calibration``). Re-running creates no duplicates. ``7×8`` and ``8×7`` are
   separate items.
6. **Choice cards** (e.g. -er / -é): items with ``answer_mode = choices``; the options
   keep their order (no shuffling of « -er » / « -é »).
"""
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tools.misc import mute_logger

from .common import PracticeCase


class TestDecksItems(PracticeCase):

    def test_deck_defaults_and_company(self):
        self.assertEqual(self.deck.session_size, 10)
        self.assertEqual(self.deck.company_id, self.company)
        self.assertEqual(self.deck.curriculum_item_ids, self.item_math)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.Deck.create({"name": "Bad", "session_size": 0})
            self.env.flush_all()

    def test_generator_units_items(self):
        self.assertEqual(len(self.deck.unit_ids), 8)
        self.assertEqual(len(self.t7.item_ids), 13)
        i78, i87 = self.item("7x8"), self.item("8x7")
        self.assertTrue(i78 and i87 and i78 != i87)
        self.assertEqual((i78.prompt, i78.answer, i78.answer_mode, i78.step), ("7 × 8", "56", "keypad", 8))
        self.assertIn("49", i78.hint)  # derived from 7 × 7
        self.assertTrue(self.item("7x10").calibration and self.item("7x1").calibration and self.item("7x0").calibration)
        self.assertFalse(self.item("7x8").calibration)
        steps = self.t7.item_ids.sorted("step").mapped("step")
        self.assertEqual(steps, list(range(13)))
        self.assertEqual(i78.deck_id, self.deck)

    def test_generator_idempotent(self):
        before = len(self.deck.item_ids)
        self.deck._generate_multiplication(tables=range(2, 10), upto=12)
        self.assertEqual(len(self.deck.item_ids), before)
        self.assertEqual(len(self.deck.unit_ids), 8)

    def test_key_unique_per_deck(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.PItem.create({"unit_id": self.t7.id, "key": "7x8", "prompt": "x", "answer": "1"})
            self.env.flush_all()

    def test_keypad_digits_only(self):
        with self.assertRaises(ValidationError):
            self.PItem.create({"unit_id": self.t7.id, "key": "bad", "prompt": "x", "answer": "5a"})

    def test_choice_cards(self):
        deck = self.Deck.create({"name": "Infinitive or past participle"})
        unit = self.Unit.create({"deck_id": deck.id, "name": "-er / -é"})
        deck._generate_choice_cards(unit, [
            ("c1", "Il a ___ (jouer / joué) au soccer.", [("jouer", False), ("joué", True)], "vendu fits: -é"),
            ("c2", "Pour ___ (tomber / tombé) en amour…", [("tomber", True), ("tombé", False)], "vendre fits: -er"),
        ])
        c1 = deck.item_ids.filtered(lambda i: i.key == "c1")
        self.assertEqual(c1.answer_mode, "choices")
        self.assertEqual(c1.choice_ids.sorted("sequence").mapped("label"), ["jouer", "joué"])
        self.assertEqual(c1.answer, "joué")
        self.assertTrue(c1._is_correct("joué"))
        self.assertFalse(c1._is_correct("jouer"))
        with self.assertRaises(ValidationError):
            self.PItem.create({"unit_id": unit.id, "key": "c3", "prompt": "x", "answer": "a", "answer_mode": "choices",
                               "choice_ids": [(0, 0, {"label": "a", "correct": True})]})
        with self.assertRaises(ValidationError):
            self.PItem.create({"unit_id": unit.id, "key": "c4", "prompt": "x", "answer": "a", "answer_mode": "choices",
                               "choice_ids": [(0, 0, {"label": "a", "correct": True}), (0, 0, {"label": "b", "correct": True})]})

    def test_keypad_correctness(self):
        i = self.item("7x8")
        self.assertTrue(i._is_correct("56"))
        self.assertTrue(i._is_correct(" 056 "))
        self.assertFalse(i._is_correct("54"))
        self.assertFalse(i._is_correct(""))
        self.assertTrue(self.item("7x0")._is_correct("0"))
