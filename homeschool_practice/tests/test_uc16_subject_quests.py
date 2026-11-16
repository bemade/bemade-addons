# -*- coding: utf-8 -*-
"""UC-16 — Every subject in turn: quests per deck, in rotation.

Acceptance criteria
-------------------
1. A deck may name its subject (``subject_id``, a ``homeschool.subject``: « Mathématiques »,
   « Français »…), set in the back office. The French grammar starter decks are loaded
   with the French subject.
2. Quests are drawn **per deck**, not per subject (UC-23): the slots rotate among the
   unlocked decks, so the subjects come in turn with their decks; « Homophones » and
   « Grammaire » are two decks of one subject and each gets its own turn.
3. With math and French unlocked and 3 quests a day, every deck gets its quest within a
   couple of days, even when nothing of it is due (the session then reviews what was seen).
4. A quest template is still drawn at most once a day per deck.
5. Decks without a subject rotate like the others.
"""
import random
from datetime import date, timedelta

from .common import PracticeCase

MONDAY = date(2026, 11, 16)


class NoExtra(random.Random):
    def random(self):
        return 0.99  # no surprise, no challenge: deck quests only


class TestSubjectQuests(PracticeCase):

    def setUp(self):
        super().setUp()
        self.student.practice_weekdays = "12345"
        self.deck.subject_id = self.math
        self.Deck.action_load_grammar_fr()
        self.grammar = self.Deck.search([("name", "=", "Grammaire")])
        self.homophones = self.Deck.search([("name", "=", "Homophones")])
        self.t7.action_unlock(self.student)
        self.t3.action_unlock(self.student)
        (self.grammar | self.homophones).unit_ids.action_unlock(self.student)

    def deck_quests(self, day, **kw):
        return self.Quest._draw(self.student, day, rng=NoExtra(1), **kw).filtered(lambda q: q.kind == "deck_session")

    def test_grammar_decks_are_french(self):
        self.assertEqual((self.grammar | self.homophones).subject_id, self.fle)

    def test_one_quest_per_deck(self):
        quests = self.deck_quests(MONDAY)
        self.assertEqual(quests.deck_id, self.deck | self.grammar | self.homophones)
        self.assertEqual(quests.deck_id.subject_id, self.math | self.fle)

    def test_deck_with_nothing_due_still_gets_its_turn(self):
        for unit in self.t7 | self.t3:
            self.run_session(unit=unit)
        self.shift_due(days=30)  # every math item seen and far from due
        self.assertIn(self.deck, self.deck_quests(MONDAY).deck_id)

    def test_more_decks_than_quests(self):
        self.student.practice_quests_per_day = 1
        decks = self.deck_quests(MONDAY).deck_id | self.deck_quests(MONDAY + timedelta(days=1)).deck_id \
            | self.deck_quests(MONDAY + timedelta(days=2)).deck_id
        self.assertEqual(decks, self.deck | self.grammar | self.homophones)

    def test_quests_done_in_both_subjects(self):
        self.student.practice_weekdays = "1234567"
        quests = self.Quest._draw(self.student, rng=NoExtra(1)).filtered(lambda q: q.kind == "deck_session")
        for q in quests:
            for _i in range(q.target):
                unit = q.deck_id.unit_ids._unlocked_for(self.student)[0]
                session = self.Session._start(self.student, q.deck_id, kind="unit", unit=unit)
                self.answer_all(session)
                session._finish()
            self.assertTrue(q.done, q.deck_id.name)

    def test_no_subject_rotates_too(self):
        (self.deck | self.grammar | self.homophones).subject_id = False
        self.assertEqual(self.deck_quests(MONDAY).deck_id, self.deck | self.grammar | self.homophones)
