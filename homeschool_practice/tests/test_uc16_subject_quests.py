# -*- coding: utf-8 -*-
"""UC-16 — Every subject every day: one session quest per subject.

Acceptance criteria
-------------------
1. A deck may name its subject (``subject_id``, a ``homeschool.subject``: « Mathématiques »,
   « Français »…), set in the back office. The French grammar starter decks are loaded
   with the French subject.
2. **One session quest per subject**: when the day's quests are drawn, each subject with
   units unlocked for the learner gets a ``unit_session`` quest on its unit that needs it
   most (even when nothing is due: the session then reviews what was seen), before the
   review quest and the pool. Units of decks without a subject form one group of their
   own. With more subjects than quests a day, the subjects that need it most win.
3. So with math and French unlocked and 3 quests a day, the learner gets a math session
   quest, a French session quest and one more quest: finishing all three (the default day
   goal for this setup) means practice in both subjects that day.
4. Two session quests on the same day are allowed (one per unit); a quest template is
   still drawn at most once a day per unit.
5. Families whose decks have no subject keep the previous draw (UC-07).
"""
from datetime import date

from .common import PracticeCase

MONDAY = date(2026, 11, 16)


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

    def test_grammar_decks_are_french(self):
        self.assertEqual((self.grammar | self.homophones).subject_id, self.fle)

    def test_one_session_quest_per_subject(self):
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 3)
        units = quests.filtered(lambda q: q.kind == "unit_session").unit_id
        self.assertEqual(units.deck_id.subject_id, self.math | self.fle)
        self.assertEqual(len(units), 2)
        self.assertEqual(len(quests.filtered(lambda q: q.kind != "unit_session")), 1)

    def test_subject_with_nothing_due_still_gets_its_quest(self):
        for unit in self.t7 | self.t3:
            self.run_session(unit=unit)
        self.shift_due(days=30)  # every math item seen and far from due
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertIn(self.math, quests.filtered(lambda q: q.kind == "unit_session").unit_id.deck_id.subject_id)

    def test_more_subjects_than_quests(self):
        self.student.practice_quests_per_day = 1
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests), 1)
        self.assertEqual(quests.kind, "unit_session")

    def test_quests_done_in_both_subjects(self):
        self.student.practice_weekdays = "1234567"
        quests = self.Quest._draw(self.student)
        for q in quests.filtered(lambda q: q.kind == "unit_session"):
            session = self.Session._start(self.student, q.unit_id.deck_id, kind="unit", unit=q.unit_id)
            self.answer_all(session)
            session._finish()
            self.assertTrue(q.done, q.unit_id.name)

    def test_no_subject_keeps_previous_draw(self):
        (self.deck | self.grammar | self.homophones).subject_id = False
        quests = self.Quest._draw(self.student, MONDAY)
        self.assertEqual(len(quests.filtered(lambda q: q.kind == "unit_session")), 1)
