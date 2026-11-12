# -*- coding: utf-8 -*-
"""UC-14 — Free practice: the learner picks exactly which units to practice.

Acceptance criteria
-------------------
1. From « Pratique libre », tapping a deck opens a picker listing that deck's units
   **unlocked for the learner** (never a locked one), as large toggles, with an « All »
   toggle and « Start ». Every unit is selected the first time; the last choice per deck
   is remembered on the device (a convenience only: the page works without it).
2. A ``free`` session (``kind = free``) carries the chosen units (``unit_ids``) and draws
   **only** from them: due items first, then newly introduced ones (at most
   ``max_new_per_session``), then the rest of their seen items, repeated to the session
   size like any session. No review items from units he did not pick.
3. A ``free`` session needs at least one unit; units not unlocked for the learner are
   dropped by the engine and refused by the API (access error), as are units of another
   deck.
4. Quests: a free session on a single unit counts for that unit's « session » quest;
   on several units it counts for none of the unit or review quests. Answers, hints,
   perfect sessions, XP, goals and badges count as for any session.
5. Without a choice (old clients, a ``deck_id`` alone) the API keeps choosing for him.
6. Back office: the session shows its chosen units.
"""
import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import API, PracticeCase, PracticeHttpCase


@tagged("post_install", "-at_install")
class TestFreePractice(PracticeCase):

    def setUp(self):
        super().setUp()
        self.t5 = self.deck.unit_ids.filtered(lambda u: u.sequence == 5)
        for unit in self.t3 | self.t5 | self.t7:
            unit.action_unlock(self.student)

    def units_served(self, session):
        return self.PItem.browse(json.loads(session.queue)).unit_id

    def test_only_the_chosen_units(self):
        self.run_session(unit=self.t5)
        self.run_session(unit=self.t7)
        self.shift_due()
        session = self.Session._start(self.student, self.deck, kind="free", units=self.t3)
        self.assertEqual(session.kind, "free")
        self.assertEqual(session.unit_ids, self.t3)
        self.assertEqual(self.units_served(session), self.t3)
        self.assertEqual(len(json.loads(session.queue)), self.deck.session_size)

    def test_several_units(self):
        self.run_session(unit=self.t3)
        self.run_session(unit=self.t7)
        self.run_session(unit=self.t5)
        self.shift_due()
        session = self.Session._start(self.student, self.deck, kind="free", units=self.t3 | self.t7)
        self.assertEqual(self.units_served(session), self.t3 | self.t7)

    def test_needs_units_and_drops_locked(self):
        with self.assertRaises(ValidationError), mute_logger("odoo.sql_db"):
            self.Session._start(self.student, self.deck, kind="free", units=self.Unit)
        t9 = self.deck.unit_ids.filtered(lambda u: u.sequence == 9)
        session = self.Session._start(self.student, self.deck, kind="free", units=self.t3 | t9)
        self.assertNotIn(t9, self.units_served(session))

    def test_quests(self):
        self.student.practice_weekdays = "1234567"
        quests = self.Quest._draw(self.student)
        unit_q = quests.filtered(lambda q: q.kind == "unit_session")
        other = (self.t3 | self.t5 | self.t7) - unit_q.unit_id
        both = self.Session._start(self.student, self.deck, kind="free", units=unit_q.unit_id | other[0])
        self.answer_all(both)
        both._finish()
        self.assertFalse(unit_q.done)
        single = self.Session._start(self.student, self.deck, kind="free", units=unit_q.unit_id)
        self.answer_all(single)
        single._finish()
        self.assertTrue(unit_q.done)


@tagged("post_install", "-at_install")
class TestFreePracticeApi(PracticeHttpCase):

    def assertDenied(self, path, **params):
        r = self.url_open(API + path, data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}),
                          headers={"Content-Type": "application/json"})
        body = r.json()
        self.assertIn("error", body)
        self.assertRegex(body["error"]["data"]["name"], "Forbidden|NotFound")

    def test_picker_lists_unlocked_units_only(self):
        self.authenticate("hs_learner", "hs_learner")
        deck = self.call("/home")["decks"][0]
        self.assertEqual([u["name"] for u in deck["units"]], ["table de 7"])
        self.assertEqual(set(deck["units"][0]), {"id", "name"})

    def test_start_with_choice(self):
        self.authenticate("hs_learner", "hs_learner")
        deck = self.call("/home")["decks"][0]
        res = self.call("/session/start", deck_id=deck["id"], unit_ids=[deck["units"][0]["id"]])
        self.assertTrue(res["item"])
        session = self.env["homeschool.practice.session"].browse(res["session_id"])
        self.assertEqual(session.kind, "free")
        self.assertEqual(session.unit_ids.mapped("sequence"), [7])

    def test_locked_or_foreign_unit_refused(self):
        t3 = self.deck.unit_ids.filtered(lambda u: u.sequence == 3)
        other_deck = self.env["homeschool.practice.deck"].create({"name": "Other"})
        other_deck._generate_multiplication(tables=[7], upto=12)
        self.authenticate("hs_learner", "hs_learner")
        with mute_logger("odoo.http"):
            self.assertDenied("/session/start", deck_id=self.deck.id, unit_ids=[t3.id])
            self.assertDenied("/session/start", deck_id=self.deck.id, unit_ids=[other_deck.unit_ids.id])

    def test_no_choice_keeps_old_behaviour(self):
        self.authenticate("hs_learner", "hs_learner")
        res = self.call("/session/start", deck_id=self.deck.id)
        session = self.env["homeschool.practice.session"].browse(res["session_id"])
        self.assertIn(session.kind, ("unit", "review"))

    def test_screen_has_picker(self):
        self.authenticate("hs_learner", "hs_learner")
        self.assertEqual(self.call("/home")["labels"]["pick"], "Choisis ce que tu veux pratiquer")
        js = self.url_open("/homeschool_practice/static/src/js/practice.js").text
        self.assertIn("function picker(", js)
        self.assertIn("unit_ids", js)
