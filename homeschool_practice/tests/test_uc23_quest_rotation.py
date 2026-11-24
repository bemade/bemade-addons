# -*- coding: utf-8 -*-
"""UC-23 — The day's quests: tables until mastered, a rotation, surprise lessons, 3–5 sessions.

Acceptance criteria
-------------------
1. **Tables until mastered.** A deck flagged « Une quête chaque jour jusqu'à la maîtrise »
   (``quest_daily``, the times tables) gets a deck session quest every practice day while
   it is not mastered by the learner: mastered = every item of the deck is ``automatic``
   for him (the module's mastery verdict). Once mastered, it joins the rotation. This
   stays backend only: no mastery wording on the learner's screen.
2. **Three quests a day** (the learner's ``practice_quests_per_day``), each on a different
   deck: the other slots rotate among the unlocked decks, least recently quested first
   (ties: the deck with the most due or new cards). A deck never gets two quests a day.
3. **Sizes:** a deck quest asks for 1 to 3 sessions of that deck (``deck_session``: any
   finished session of any unit of the deck counts). The draw sets the targets so the
   day asks for **3 to 5 sessions** in total, and varies it (not always 3). A « perfect »
   or « no hint » quest may take a rotation slot (1 to 2 sessions' worth).
4. **Surprise lessons** (``surprise``, target 1–2): drawn on about one day in three, only
   when an unlocked unit was not practised for 5 days or never. Starting it opens a unit
   session on the unit the system picks: the unlocked unit practised longest ago (never
   practised first; tie: most due cards), outside the day's other quest decks when
   possible. Every finished surprise session counts.
5. The draw's randomness is injectable (``_draw(student, day, rng=...)``); without it the
   draw is seeded by learner and day (idempotent anyway: drawn once a day).
6. The reward is unchanged: the day's goal still pays the family's rule when the quests
   are done. Everything is per learner.
"""
import random
from collections import Counter
from datetime import date, timedelta

from odoo import fields
from odoo.tests import tagged

from .common import PracticeCase, PracticeHttpCase

MONDAY = date(2026, 11, 16)


class FixedRng(random.Random):
    """A seeded RNG whose ``random()`` always returns ``value`` (forces the surprise roll)."""

    def __init__(self, value, seed=0):
        super().__init__(seed)
        self.value = value

    def random(self):
        return self.value


def session_total(quests):
    """The day's sessions, counted distinct (UC-29: a challenge is done in the others' sessions)."""
    return quests._distinct_sessions()


@tagged("post_install", "-at_install")
class TestQuestRotation(PracticeCase):

    def setUp(self):
        super().setUp()
        self.deck.write({"subject_id": self.math.id, "quest_daily": True})
        self.Deck.action_load_grammar_fr()
        self.Deck.action_load_math()
        self.Deck.action_load_english()
        self.grammar = self.Deck.search([("name", "=", "Grammaire")])
        self.homophones = self.Deck.search([("name", "=", "Homophones")])
        self.fractions = self.Deck.search([("name", "=", "Les fractions")])
        self.english = self.Deck.search([("name", "=", "English grammar")])
        (self.t7 | self.t3).action_unlock(self.student)
        (self.grammar | self.homophones).unit_ids.action_unlock(self.student)
        self.fractions.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)
        self.english.unit_ids.filtered(lambda u: u.sequence <= 3).action_unlock(self.student)
        self.rotation = self.grammar | self.homophones | self.fractions | self.english

    def deck_quests(self, quests):
        return quests.filtered(lambda q: q.kind == "deck_session")

    def master_tables(self):
        self.deck.unit_ids.action_unlock(self.student)
        for item in self.deck.item_ids:
            row = self.mastery(item) or self.Mastery.create({"student_id": self.student.id, "item_id": item.id})
            row.state = "automatic"

    def simulate(self, days, seed=7, start=MONDAY):
        rng = random.Random(seed)
        return [self.Quest._draw(self.student, start + timedelta(days=d), rng=rng) for d in range(days)]

    # 1. tables until mastered -------------------------------------------------
    def test_tables_every_day_until_mastered(self):
        for quests in self.simulate(20):
            self.assertEqual(len(quests), 3)
            tables = self.deck_quests(quests).filtered(lambda q: q.deck_id == self.deck)
            self.assertEqual(len(tables), 1, quests.mapped("label"))
            self.assertEqual(quests.sorted("sequence")[0], tables)

    def test_tables_join_the_rotation_once_mastered(self):
        self.assertFalse(self.deck._mastered_by(self.student))
        self.master_tables()
        self.assertTrue(self.deck._mastered_by(self.student))
        days = self.simulate(20)
        with_tables = [q for q in days if self.deck in self.deck_quests(q).deck_id]
        self.assertTrue(with_tables, "the tables still come back in the rotation")
        self.assertLess(len(with_tables), 15, "but not every day any more")

    def test_one_missed_fact_brings_the_tables_back(self):
        self.master_tables()
        self.mastery(self.item("7x8")).state = "derived"
        self.assertFalse(self.deck._mastered_by(self.student))

    def test_mastery_is_per_learner(self):
        self.master_tables()
        other = self.env["homeschool.student"].create({"partner_id": self.env["res.partner"].create({"name": "Other"}).id})
        self.assertFalse(self.deck._mastered_by(other))

    # 2. rotation ----------------------------------------------------------------
    def test_three_quests_each_on_another_deck(self):
        for quests in self.simulate(30):
            self.assertEqual(len(quests), 3)
            decks = self.deck_quests(quests).deck_id
            self.assertEqual(len(decks), len(self.deck_quests(quests)), "a deck twice the same day")

    def test_least_recently_quested_first(self):
        no_extra = FixedRng(0.99)
        day1 = self.deck_quests(self.Quest._draw(self.student, MONDAY, rng=no_extra)).deck_id - self.deck
        self.assertEqual(len(day1), 2)
        day2 = self.deck_quests(self.Quest._draw(self.student, MONDAY + timedelta(days=1), rng=no_extra)).deck_id - self.deck
        self.assertEqual(len(day2), 2)
        self.assertFalse(day1 & day2, "yesterday's decks wait for the others")
        self.assertEqual(day1 | day2, self.rotation)

    def test_ties_go_to_the_most_due(self):
        need = Counter()
        for unit, count, _due in self.student._practice_needs(MONDAY):
            need[unit.deck_id] += count
        best = max(self.rotation, key=lambda d: (need[d], -d.sequence, -d.id))
        quests = self.Quest._draw(self.student, MONDAY, rng=FixedRng(0.99))
        self.assertEqual(self.deck_quests(quests).sorted("sequence")[1].deck_id, best)

    def test_rotation_covers_every_deck(self):
        seen = Counter()
        for quests in self.simulate(10):
            seen.update(self.deck_quests(quests).deck_id.ids)
        for deck in self.rotation:
            self.assertGreaterEqual(seen[deck.id], 2, deck.name)

    def test_few_decks_still_three_quests(self):
        (self.rotation.unit_ids).action_lock(self.student)
        for quests in self.simulate(5):
            self.assertEqual(len(quests), 3)
            self.assertEqual(self.deck_quests(quests).deck_id, self.deck)
            self.assertTrue(3 <= session_total(quests) <= 5)

    # 3. sizes ------------------------------------------------------------------
    def test_three_to_five_sessions_with_variety(self):
        totals = Counter()
        for quests in self.simulate(120, seed=11):
            total = session_total(quests)
            self.assertTrue(3 <= total <= 5, quests.mapped("label"))
            totals[total] += 1
            for q in quests:
                self.assertTrue(1 <= q.sessions <= (3 if q.kind == "deck_session" else 2), q.label)
        self.assertEqual(set(totals), {3, 4, 5})
        self.assertGreater(totals[4] + totals[5], 30, "some days ask for more than 3 sessions")

    def test_deck_quest_counts_any_unit_of_its_deck(self):
        quests = self.Quest._draw(self.student, rng=FixedRng(0.99))
        q = self.deck_quests(quests).filtered(lambda q: q.deck_id == self.deck)
        q.target = 2
        for unit in self.t3 | self.t7:
            self.run_session(unit=unit)
        self.assertTrue(q.done)
        self.assertEqual(q.label, "2 sessions: Times tables")

    def test_challenge_quests_sometimes(self):
        kinds = Counter()
        for quests in self.simulate(120, seed=3):
            kinds.update(quests.mapped("kind"))
        self.assertTrue(kinds["perfect"] + kinds["no_hint"] > 0)
        self.assertGreater(kinds["deck_session"], kinds["perfect"] + kinds["no_hint"])

    # 4. surprise lessons ---------------------------------------------------------
    def test_surprise_about_one_day_in_three(self):
        days = self.simulate(150, seed=5)
        share = sum(1 for q in days if "surprise" in q.mapped("kind")) / len(days)
        self.assertTrue(0.2 < share < 0.45, share)

    def test_no_surprise_without_a_stale_unit(self):
        self.practise_all()
        quests = self.Quest._draw(self.student, rng=FixedRng(0.0))
        self.assertNotIn("surprise", quests.mapped("kind"))

    def practise_all(self):
        for unit in self.Unit.search([])._unlocked_for(self.student):
            s = self.Session._start(self.student, unit.deck_id, kind="unit", unit=unit)
            self.answer_all(s, stop=1)
            s._finish()

    def age(self, unit, days):
        self.Session.search([("student_id", "=", self.student.id), ("unit_id", "=", unit.id)]).write(
            {"started_at": fields.Datetime.now() - timedelta(days=days)})

    def test_surprise_picks_the_stalest_unit(self):
        quests = self.Quest._draw(self.student, rng=FixedRng(0.0))
        surprise = quests.filtered(lambda q: q.kind == "surprise")
        self.assertEqual(len(surprise), 1)
        self.assertEqual(surprise.label, "%s surprise lesson%s" % (surprise.target, "s" if surprise.target > 1 else ""))
        quest_decks = self.deck_quests(quests).deck_id
        outside = (self.rotation - quest_decks).sorted("sequence")[0]
        inside = (self.rotation & quest_decks)[:1]
        self.practise_all()
        stale = outside.unit_ids._unlocked_for(self.student).sorted("sequence")[0]
        self.age(stale, 20)
        self.assertEqual(surprise._surprise_unit(), stale)
        # a unit of the day's other quest decks, even staler, is skipped when possible
        if inside:
            self.age(inside.unit_ids._unlocked_for(self.student)[0], 40)
            self.assertEqual(surprise._surprise_unit(), stale)
        # the session it opens counts for the quest
        s = self.Session._start(self.student, stale.deck_id, kind="unit", unit=stale, quest=surprise)
        self.answer_all(s)
        s._finish()
        self.assertEqual(surprise.progress, 1)

    def test_never_practised_first(self):
        quests = self.Quest._draw(self.student, rng=FixedRng(0.0))
        surprise = quests.filtered(lambda q: q.kind == "surprise")
        unlocked = self.Unit.search([])._unlocked_for(self.student)
        fresh = self.english.unit_ids.sorted("sequence")[2]
        for unit in unlocked - fresh:
            s = self.Session._start(self.student, unit.deck_id, kind="unit", unit=unit)
            self.answer_all(s, stop=1)
            s._finish()
        self.assertEqual(surprise._surprise_unit(), fresh)

    def test_other_sessions_do_not_count_for_surprise(self):
        surprise = self.Quest._draw(self.student, rng=FixedRng(0.0)).filtered(lambda q: q.kind == "surprise")
        self.run_session(unit=self.t7)
        self.assertEqual(surprise.progress, 0)

    # 6. reward unchanged, per learner -------------------------------------------
    def test_reward_unchanged(self):
        rtype = self.env["homeschool.reward.type"].create({"name": "Gaming time", "unit": "min"})
        self.env["homeschool.reward.rule"].create({"student_id": self.student.id, "goal_period": "day",
                                                    "reward_type_id": rtype.id, "amount": 10, "date_from": "2026-01-01"})
        self.env["homeschool.practice.goal"].create({"student_id": self.student.id, "period": "day", "target": 3})
        quests = self.Quest._draw(self.student)
        today = quests[:1].day
        for q in quests:
            q._bump(q.target)
        new = self.student._practice_check_goals(today)
        for ach in new:
            self.student._practice_earn(ach)
        self.assertEqual(self.student._reward_balance(rtype), 10)

    def test_per_learner_rotation(self):
        other = self.env["homeschool.student"].create({
            "partner_id": self.env["res.partner"].create({"name": "Other"}).id, "practice_weekdays": "1234567"})
        (self.t7 | self.t3).action_unlock(other)
        self.rotation.unit_ids.action_unlock(other)
        mine = self.Quest._draw(self.student, MONDAY, rng=FixedRng(0.99))
        theirs = self.Quest._draw(other, MONDAY, rng=FixedRng(0.99))
        self.assertEqual(mine.student_id, self.student)
        self.assertEqual(theirs.student_id, other)
        # my quests do not push the other learner's rotation
        self.assertEqual(self.deck_quests(self.Quest._draw(other, MONDAY + timedelta(days=1), rng=FixedRng(0.99))).deck_id
                         & self.deck_quests(theirs).deck_id, self.deck)

    def test_no_mastery_wording_for_the_learner(self):
        if not self.env["res.lang"]._lang_get("fr_CA"):
            self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(["homeschool_practice"], ["fr_CA"], overwrite=True)
        for quests in self.simulate(10):
            for q in quests.with_context(lang="fr_CA"):
                self.assertNotRegex(q.label.lower(), r"ma[iî]tri|master")


@tagged("post_install", "-at_install")
class TestSurpriseApi(PracticeHttpCase):

    def test_surprise_from_the_quest_card(self):
        t3 = self.deck.unit_ids.filtered(lambda u: u.sequence == 3)
        t3.action_unlock(self.student)
        t7 = self.deck.unit_ids.filtered(lambda u: u.sequence == 7)
        # the 7 table was practised: the 3 table (never practised) is the surprise
        Session = self.env["homeschool.practice.session"]
        s = Session._start(self.student, self.deck, kind="unit", unit=t7)
        item = s._current_item()
        s._answer(item, item.answer)
        s._finish()
        Quest = self.env["homeschool.practice.quest"]
        today = Quest._today(self.student)
        surprise = Quest.create({"student_id": self.student.id, "day": today, "target": 1,
                                 "template_id": self.env.ref("homeschool_practice.quest_surprise").id})
        self.authenticate("hs_learner", "hs_learner")
        home = self.call("/home")
        card = [q for q in home["quests"] if q["id"] == surprise.id][0]
        self.assertEqual(card["kind"], "surprise")
        self.assertIn("surprise", card["label"])
        res = self.call("/session/start", quest_id=surprise.id, input_type="touch", device="iPad")
        session = Session.browse(res["session_id"])
        self.assertEqual(session.unit_id, t3)
        self.assertEqual(session.quest_id, surprise)
        item = res["item"]
        n = 0
        while item and n < 40:
            out = self.call("/session/answer", session_id=res["session_id"], item_id=item["item_id"],
                            given=self.env["homeschool.practice.item"].browse(item["item_id"]).answer,
                            first_touch_ms=900, submit_ms=1400, client_uuid="s%s" % n)
            item = out.get("next")
            n += 1
        self.assertTrue(surprise.done)
