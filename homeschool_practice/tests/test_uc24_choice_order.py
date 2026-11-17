# -*- coding: utf-8 -*-
"""UC-24 — The right answer is not always in the same place.

Acceptance criteria
-------------------
1. A choices card shows its options in a fresh random order each time it is served
   (``item._display_choices()``), so the position of the right answer cannot be learned:
   over many servings of one card, the right answer appears in every position.
2. A unit whose cards all offer the same set of options (« a » ou « à », plus petite /
   égale / plus grande que 1/2, avoir / être) keeps the written order: there the position
   says nothing about the answer, and a stable order is easier to read.
3. The API item payload uses that order; the answer stays the label (judging is by label).
4. A keypad card has no choices.
"""
import random

from odoo.tests import tagged

from .common import PracticeCase


@tagged("post_install", "-at_install")
class TestChoiceOrder(PracticeCase):

    def setUp(self):
        super().setUp()
        self.deck2 = self.env["homeschool.practice.deck"].create({"name": "Order deck"})
        Unit = self.env["homeschool.practice.unit"]
        self.verbs = Unit.create({"deck_id": self.deck2.id, "name": "Find the verb", "sequence": 1})
        self.deck2._generate_choice_cards(self.verbs, [
            ("v1", "Le chien court.", [("chien", False), ("court", True), ("parc", False)], ""),
            ("v2", "Le vent souffle.", [("vent", False), ("souffle", True), ("fort", False)], ""),
        ])
        self.fixed = Unit.create({"deck_id": self.deck2.id, "name": "a or à", "sequence": 2})
        self.deck2._generate_choice_cards(self.fixed, [
            ("f1", "Il ___ un chat.", [("a", True), ("à", False)], ""),
            ("f2", "Il va ___ Montréal.", [("a", False), ("à", True)], ""),
        ])

    def test_varied_unit_is_shuffled(self):
        item = self.verbs.item_ids.filtered(lambda i: i.key == "v1")
        positions = set()
        rng = random.Random(7)
        for _ in range(60):
            labels = item._display_choices(rng=rng)
            self.assertEqual(sorted(labels), ["chien", "court", "parc"])
            positions.add(labels.index(item.answer))
        self.assertEqual(positions, {0, 1, 2})

    def test_fixed_set_unit_keeps_order(self):
        for item in self.fixed.item_ids:
            for _ in range(10):
                self.assertEqual(item._display_choices(), ["a", "à"])

    def test_keypad_has_no_choices(self):
        item = self.deck.item_ids.filtered(lambda i: i.answer_mode == "keypad")[:1]
        self.assertTrue(item)
        self.assertEqual(item._display_choices(), [])
