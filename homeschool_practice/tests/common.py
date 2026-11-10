# -*- coding: utf-8 -*-
"""Shared fixtures for the practice tests. Everything is synthetic."""
from datetime import timedelta

from odoo import fields

from odoo.addons.homeschool.tests.common import HomeschoolCase


class PracticeCase(HomeschoolCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Deck = cls.env["homeschool.practice.deck"]
        cls.Unit = cls.env["homeschool.practice.unit"]
        cls.PItem = cls.env["homeschool.practice.item"]
        cls.Session = cls.env["homeschool.practice.session"]
        cls.Attempt = cls.env["homeschool.practice.attempt"]
        cls.Mastery = cls.env["homeschool.practice.mastery"]
        cls.Quest = cls.env["homeschool.practice.quest"]
        cls.Xp = cls.env["homeschool.practice.xp"]
        cls.deck = cls.Deck.create({"name": "Times tables", "curriculum_item_ids": [fields.Command.link(cls.item_math.id)]})
        cls.deck._generate_multiplication(tables=range(2, 10), upto=12)
        cls.t7 = cls.deck.unit_ids.filtered(lambda u: u.sequence == 7)
        cls.t3 = cls.deck.unit_ids.filtered(lambda u: u.sequence == 3)
        cls.student.practice_weekdays = "1234567"

    def item(self, key):
        return self.deck.item_ids.filtered(lambda i: i.key == key)

    def mastery(self, item, student=None):
        return self.Mastery.search([("student_id", "=", (student or self.student).id), ("item_id", "=", item.id)])

    def answer_all(self, session, right=True, first_touch=900, hint=False, stop=None):
        """Answer every item served (right or wrong); returns the events of each answer."""
        out = []
        n = 0
        while session._current_item() and (stop is None or n < stop):
            item = session._current_item()
            given = item.answer if right else ("999" if item.answer_mode == "keypad" else "?")
            out.append(session._answer(item, given, hint_used=hint, first_touch_ms=first_touch, submit_ms=first_touch + 400)[1])
            n += 1
        return out

    def run_session(self, unit=None, kind=None, right=True, first_touch=900, input_type="touch"):
        session = self.Session._start(self.student, self.deck, kind=kind or ("unit" if unit else "review"),
                                      unit=unit, input_type=input_type)
        self.answer_all(session, right=right, first_touch=first_touch)
        session._finish()
        return session

    def shift_due(self, days=-30):
        """Make every mastery row of the student due (as if days had passed)."""
        rows = self.Mastery.search([("student_id", "=", self.student.id)])
        rows.write({"due_on": fields.Date.today() + timedelta(days=days)})
