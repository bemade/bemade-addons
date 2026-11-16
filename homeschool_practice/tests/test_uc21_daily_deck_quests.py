# -*- coding: utf-8 -*-
"""UC-21 — A quest every day for some decks (times tables, grammar).

Acceptance criteria
-------------------
1. A deck may be flagged « Une quête chaque jour » (``quest_daily``). The « Grammaire »
   starter deck is loaded with the flag; on databases that already hold the decks, the
   upgrade flags « Grammaire » and the times-tables deck (``deck._flag_daily_decks()``).
2. When the day's quests are drawn, each flagged deck with a unit unlocked for the learner
   gets a ``unit_session`` quest first, on its unit that needs it most.
3. The remaining slots are drawn as before among the other units: one session quest per
   subject on the unit that needs it most, then a review, then the pool. So with times
   tables and grammar flagged and units unlocked in both, every day's draw holds a tables
   quest and a grammar quest, and the third is need-first among the rest.
4. The learner's number of quests a day still holds: with more flagged decks than slots,
   the flagged decks that need it most take them all.
5. With only times tables unlocked, the draw still fills its 3 quests (review, pool).
"""
from datetime import date, timedelta

from odoo.tests import tagged

from .common import PracticeCase

MONDAY = date(2026, 11, 16)


@tagged("post_install", "-at_install")
class TestDailyDeckQuests(PracticeCase):

    def setUp(self):
        super().setUp()
        self.student.practice_weekdays = "12345"
        self.deck.write({"subject_id": self.math.id, "quest_daily": True})
        self.Deck.action_load_grammar_fr()
        self.Deck.action_load_math()
        self.grammar = self.Deck.search([("name", "=", "Grammaire")])
        self.homophones = self.Deck.search([("name", "=", "Homophones")])
        self.fractions = self.Deck.search([("name", "=", "Les fractions")])
        (self.t7 | self.t3).action_unlock(self.student)
        (self.grammar | self.homophones).unit_ids.action_unlock(self.student)
        self.fractions.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)

    def sessions(self, quests):
        return quests.filtered(lambda q: q.kind == "unit_session")

    def test_flag_loaded_on_grammar_only(self):
        self.assertTrue(self.grammar.quest_daily)
        self.assertFalse(any((self.homophones | self.fractions).mapped("quest_daily")))

    def test_flag_daily_decks_on_existing_databases(self):
        decks = self.deck | self.grammar
        decks.quest_daily = False
        self.Deck._flag_daily_decks()
        self.assertEqual(decks.mapped("quest_daily"), [True, True])
        self.assertFalse(any((self.homophones | self.fractions).mapped("quest_daily")))

    def test_tables_and_grammar_every_day(self):
        for offset in range(5):
            quests = self.Quest._draw(self.student, MONDAY + timedelta(days=offset))
            self.assertEqual(len(quests), 3)
            decks = self.sessions(quests).deck_id
            self.assertIn(self.deck, decks)
            self.assertIn(self.grammar, decks)

    def test_third_is_need_first_among_the_rest(self):
        rest = [n for n in self.student._practice_needs(MONDAY) if not n[0].deck_id.quest_daily]
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(quests.sorted("sequence")[:2].deck_id, self.deck | self.grammar)
        third = quests.sorted("sequence")[2]
        self.assertEqual(third.kind, "unit_session")
        self.assertEqual(third.unit_id, rest[0][0])
        # one quest per daily deck: the other unlocked tables unit does not get a second one
        self.assertEqual(len(self.sessions(quests).filtered(lambda q: q.deck_id == self.deck)), 1)

    def test_daily_decks_win_the_slots(self):
        self.student.practice_quests_per_day = 2
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(self.sessions(quests).deck_id, self.deck | self.grammar)
        self.assertEqual(len(quests), 2)

    def test_daily_deck_without_unlocked_unit(self):
        self.grammar.unit_ids.action_lock(self.student)
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 3)
        self.assertNotIn(self.grammar, quests.deck_id)
        self.assertIn(self.deck, self.sessions(quests).deck_id)

    def test_only_tables_unlocked_still_fills(self):
        ((self.grammar | self.homophones | self.fractions).unit_ids).action_lock(self.student)
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 3)
        self.assertEqual(self.sessions(quests).deck_id, self.deck)
        self.assertEqual(len(self.sessions(quests)), 1)
