# -*- coding: utf-8 -*-
"""Shared fixtures for the practice tests. Everything is synthetic."""
import json
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, new_test_user

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


API = "/my/homeschool/practice/api"


class PracticeHttpCase(HttpCase):
    """The learner (portal, fr_CA), his teacher (resource user) and another learner, with the
    7 table unlocked, a reward type and today's practice enabled. Everything is invented."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        if not env["res.lang"]._lang_get("fr_CA"):
            env["res.lang"]._activate_lang("fr_CA")
        env["ir.module.module"]._load_module_terms(["homeschool_practice", "homeschool_portal", "homeschool"], ["fr_CA"], overwrite=True)
        portal = env.ref("base.group_portal")
        cls.partner = env["res.partner"].create({"name": "Test Learner"})
        cls.student = env["homeschool.student"].create({"partner_id": cls.partner.id, "practice_weekdays": "1234567"})
        cls.learner = new_test_user(env, login="hs_learner", groups="base.group_portal", lang="fr_CA",
                                    partner_id=cls.partner.id, tz="America/Toronto")
        cls.student.user_id = cls.learner
        cls.teacher = new_test_user(env, login="hs_teacher", groups="base.group_portal")
        cls.student.resource_user_ids = [fields.Command.link(cls.teacher.id)]
        other_partner = env["res.partner"].create({"name": "Other Learner"})
        cls.other_student = env["homeschool.student"].create({"partner_id": other_partner.id})
        cls.other = new_test_user(env, login="hs_other", groups="base.group_portal", partner_id=other_partner.id)
        cls.other_student.user_id = cls.other
        cls.deck = env["homeschool.practice.deck"].create({"name": "Times tables"})
        cls.deck._generate_multiplication(tables=[3, 7], upto=12)
        cls.deck.unit_ids.filtered(lambda u: u.sequence == 7).action_unlock(cls.student)
        rt = env["homeschool.reward.type"].create({"name": "Gaming time", "unit": "min"})
        rt.with_context(lang="fr_CA").name = "Temps de jeu"

    def call(self, path, **params):
        r = self.url_open(API + path, data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
                          headers={"Content-Type": "application/json"})
        self.assertEqual(r.status_code, 200, r.text[:300])
        body = r.json()
        self.assertNotIn("error", body, body.get("error"))
        return body["result"]
