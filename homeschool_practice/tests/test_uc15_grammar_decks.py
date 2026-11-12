# -*- coding: utf-8 -*-
"""UC-15 — French grammar starter decks (choice cards).

Acceptance criteria
-------------------
1. A parent (homeschool manager) loads the French grammar starter decks from the deck
   list (``deck.action_load_grammar_fr()``): two decks of choice cards, in the current
   company —
   - « Homophones »: units ``« a » ou « à »`` and ``« ce » ou « se »``;
   - « Grammaire »: units « Le verbe », « Le sujet », « Nom, déterminant ou adjectif »
     and « Accords dans le GN ».
2. Every unit has an intro (the rule, with a worked example) and at least 12 cards;
   every card has exactly one correct option, options in a fixed order (« a » before
   « à »), and a hint (the test to apply). Easier cards come first (``step``).
3. Loading again creates no duplicates (decks, units and cards are matched by name and
   key); cards a parent added or edited are kept.
4. Only a parent loads them (access error otherwise).
5. Like every unit, they stay locked until a parent unlocks them for a learner; once
   unlocked, a session serves that unit's cards and accepts the right option. The concepts
   are already taught, so the decks introduce 10 cards at unlock and up to 10 new cards per
   session: a first session shows 10 different sentences, not 3 sentences repeated.
6. The content is synthetic and generic: no learner's name in any card.
"""
import json

from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import PracticeCase

UNITS = {
    "Homophones": ["« a » ou « à »", "« ce » ou « se »"],
    "Grammaire": ["Le verbe", "Le sujet", "Nom, déterminant ou adjectif", "Accords dans le GN"],
}


@tagged("post_install", "-at_install")
class TestGrammarDecks(PracticeCase):

    def load(self):
        self.Deck.action_load_grammar_fr()
        return self.Deck.search([("name", "in", list(UNITS))])

    def test_decks_and_units(self):
        decks = self.load()
        self.assertEqual(sorted(decks.mapped("name")), sorted(UNITS))
        for deck in decks:
            self.assertEqual(deck.company_id, self.env.company)
            self.assertEqual(deck.unit_ids.sorted("sequence").mapped("name"), UNITS[deck.name])

    def test_cards(self):
        for unit in self.load().unit_ids:
            self.assertTrue(unit.intro, unit.name)
            self.assertGreaterEqual(len(unit.item_ids), 12, unit.name)
            for item in unit.item_ids:
                self.assertEqual(item.answer_mode, "choices")
                self.assertEqual(len(item.choice_ids.filtered("correct")), 1, item.key)
                self.assertEqual(item.answer, item.choice_ids.filtered("correct").label)
                self.assertTrue(item.hint, item.key)
        card = self.PItem.search([("prompt", "=", "Il ___ un vélo rouge.")])
        self.assertEqual(card.choice_ids.sorted("sequence").mapped("label"), ["a", "à"])
        self.assertEqual(card.answer, "a")
        self.assertEqual(card.step, min(card.unit_id.item_ids.mapped("step")))

    def test_idempotent_keeps_edits(self):
        decks = self.load()
        card = decks.item_ids.sorted("id")[0]
        card.hint = "Ma propre astuce"
        extra = self.PItem.create({
            "unit_id": card.unit_id.id, "key": "parent-1", "prompt": "Elle ___ un chat.", "answer": "a",
            "answer_mode": "choices", "hint": "avait",
            "choice_ids": [(0, 0, {"label": "a", "correct": True}), (0, 0, {"label": "à"})],
        })
        counts = (len(decks), len(decks.unit_ids), len(decks.item_ids))
        decks = self.load()
        self.assertEqual((len(decks), len(decks.unit_ids), len(decks.item_ids)), counts)
        self.assertEqual(card.hint, "Ma propre astuce")
        self.assertTrue(extra.exists())

    def test_parent_only(self):
        teacher = new_test_user(self.env, login="hs_not_parent", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.Deck.with_user(teacher).action_load_grammar_fr()

    def test_locked_until_unlocked_then_playable(self):
        decks = self.load()
        unit = decks.unit_ids.filtered(lambda u: u.name == "« a » ou « à »")
        self.assertFalse(unit._unlocked_for(self.student))
        unit.action_unlock(self.student)
        session = self.Session._start(self.student, unit.deck_id, kind="unit", unit=unit)
        item = session._current_item()
        self.assertEqual(item.unit_id, unit)
        self.assertEqual(len(set(json.loads(session.queue))), 10)
        self.assertTrue(session._answer(item, item.answer, first_touch_ms=900, submit_ms=1300)[0].correct)

    def test_synthetic(self):
        texts = " ".join(self.load().item_ids.mapped(lambda i: "%s %s" % (i.prompt, i.hint)))
        for name in ("Felix", "Félix", "Josée"):
            self.assertNotIn(name, texts)
