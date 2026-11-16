# -*- coding: utf-8 -*-
"""UC-21 — A quest every day until mastered (the times tables).

Acceptance criteria
-------------------
1. A deck may be flagged « Une quête chaque jour jusqu'à la maîtrise » (``quest_daily``).
   No starter deck is loaded with the flag (« Grammaire » joins the rotation); on databases
   that already hold the decks, the upgrade sets it on the times-tables decks and clears it
   on « Grammaire » (``deck._flag_daily_decks()``, idempotent).
2. When the day's quests are drawn, each flagged deck with a unit unlocked for the learner
   and not yet mastered by him gets a deck session quest first (UC-23 for mastery).
3. The remaining slots rotate among the other decks (UC-23): so with the tables flagged and
   grammar, homophones and fractions unlocked, every day holds a tables quest, and grammar
   comes back in turn, not every day.
4. The learner's number of quests a day still holds: with more flagged decks than slots,
   the flagged decks that need it most take them all.
5. With only the times tables unlocked, the draw still fills its 3 quests (surprise or
   challenge quests).
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
        return quests.filtered(lambda q: q.kind == "deck_session")

    def test_no_starter_deck_flagged(self):
        self.assertFalse(any((self.grammar | self.homophones | self.fractions).mapped("quest_daily")))

    def test_flag_daily_decks_on_existing_databases(self):
        self.deck.quest_daily = False
        self.grammar.quest_daily = True
        self.assertEqual(self.Deck._flag_daily_decks(), self.deck)
        self.assertTrue(self.deck.quest_daily)
        self.assertFalse(any((self.grammar | self.homophones | self.fractions).mapped("quest_daily")))
        self.Deck._flag_daily_decks()  # idempotent
        self.assertTrue(self.deck.quest_daily)
        self.assertFalse(self.grammar.quest_daily)

    def test_tables_every_day_grammar_in_turn(self):
        grammar_days = 0
        for offset in range(5):
            quests = self.Quest._draw(self.student, MONDAY + timedelta(days=offset))
            self.assertEqual(len(quests), 3)
            decks = self.sessions(quests).deck_id
            self.assertIn(self.deck, decks)
            grammar_days += self.grammar in decks
        self.assertTrue(1 <= grammar_days <= 4, grammar_days)

    def test_daily_decks_win_the_slots(self):
        self.grammar.quest_daily = True
        self.student.practice_quests_per_day = 2
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(self.sessions(quests).deck_id, self.deck | self.grammar)
        self.assertEqual(len(quests), 2)

    def test_daily_deck_without_unlocked_unit(self):
        (self.t7 | self.t3).action_lock(self.student)
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 3)
        self.assertNotIn(self.deck, quests.deck_id)

    def test_only_tables_unlocked_still_fills(self):
        ((self.grammar | self.homophones | self.fractions).unit_ids).action_lock(self.student)
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 3)
        self.assertEqual(self.sessions(quests).deck_id, self.deck)
        self.assertEqual(len(self.sessions(quests)), 1)
