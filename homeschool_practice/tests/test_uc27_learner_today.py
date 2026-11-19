# -*- coding: utf-8 -*-
"""UC-27 — The learner's today, in the learner's time zone.

Acceptance criteria
-------------------
1. One « learner's today » for every practice date: the learner's time zone (his user's,
   else his partner's, else the family's — the company partner's —, else
   ``America/Toronto``), whoever runs the code (the learner through the portal, a parent,
   a script or a cron with no time zone in its context).
2. In the evening in Montréal (2026-11-19 00:30 UTC = 18 Nov 19:30), from a context
   with no time zone: a unit unlocked is « unlocked on » the 18th; its introduced items
   are due on the 18th; an answer's XP counts for the 18th (and in « XP today »); a missed
   item is due again on the 18th; the day's quests are drawn for the 18th and the
   session's quests are those; a goal target changed that evening applies from the 19th.
3. A UTC moment becomes the learner's local date (``_practice_local_date``): the
   two-days rule of automaticity and the staleness of a unit use it.
4. The tutor's progress page shows « last practised » as the learner's local date:
   a ``last_seen`` of 2026-11-19 00:30 UTC reads 18 Nov.
5. The 19.0.1.8.1 migration moves ``unlocked_on`` to the learner's local date of the
   row's creation only where the bug wrote it (``unlocked_on`` = the UTC date of
   ``create_date`` and the local date differs), and recomputes an XP ``day`` that differs
   from the learner's local date of its ``date``. Other rows are left alone.
"""
import importlib.util
import os
import re
from datetime import date, datetime

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged

from .common import PracticeCase, PracticeHttpCase

EVENING = "2026-11-19 00:30:00"  # 18 Nov 19:30 in Montréal
LOCAL = date(2026, 11, 18)


class LearnerTodayCase(PracticeCase):

    def setUp(self):
        super().setUp()
        self.learner = self.portal_user(self.partner, login="uc27_learner")
        self.learner.tz = "America/Toronto"
        self.student.user_id = self.learner
        # a script / cron / shell: no time zone anywhere on the caller's side
        self.env.user.tz = False
        self.bare = self.env(context={})

    def as_script(self, record):
        return record.with_env(self.bare)


class TestPracticeTz(LearnerTodayCase):

    def test_fallback_order(self):
        student = self.student
        other = self.env["res.partner"].create({"name": "Synthetic Login"})
        user = self.portal_user(other, login="uc27_other")
        user.tz = "Asia/Tokyo"
        self.partner.tz = "Europe/Paris"
        self.company.partner_id.tz = "America/Vancouver"
        student.user_id = user
        self.assertEqual(student._practice_tz(), "Asia/Tokyo", "the learner's login first")
        student.user_id = False
        self.assertEqual(student._practice_tz(), "Europe/Paris", "then the learner's partner")
        self.partner.tz = False
        self.assertEqual(student._practice_tz(), "America/Vancouver", "then the family")
        self.company.partner_id.tz = False
        self.assertEqual(student._practice_tz(), "America/Toronto", "then Québec time")

    def test_local_date(self):
        self.assertEqual(self.student._practice_local_date(fields.Datetime.to_datetime(EVENING)), LOCAL)
        self.assertEqual(self.student._practice_local_date(EVENING), LOCAL)
        self.assertEqual(self.student._practice_local_date(datetime(2026, 11, 18, 5, 30)), date(2026, 11, 18))
        self.assertFalse(self.student._practice_local_date(False))
        with freeze_time(EVENING):
            self.assertEqual(self.as_script(self.student)._practice_today(), LOCAL)


@freeze_time(EVENING)
class TestEveningInMontreal(LearnerTodayCase):

    def setUp(self):
        super().setUp()
        # the bug's premise: a caller with no time zone is already on the 19th
        self.assertEqual(fields.Date.context_today(self.bare.user), date(2026, 11, 19))

    def unlock(self):
        self.as_script(self.t7).action_unlock(self.as_script(self.student))

    def test_unlock_and_introduce(self):
        self.unlock()
        row = self.env["homeschool.practice.unit.access"].search(
            [("student_id", "=", self.student.id), ("unit_id", "=", self.t7.id)])
        self.assertEqual(row.unlocked_on, LOCAL)
        rows = self.Mastery.search([("student_id", "=", self.student.id), ("unit_id", "=", self.t7.id)])
        self.assertTrue(rows)
        self.assertEqual(set(rows.mapped("due_on")), {LOCAL})

    def test_mastery_due_on_default(self):
        row = self.as_script(self.Mastery).create({"student_id": self.student.id, "item_id": self.item("3x4").id})
        self.assertEqual(row.due_on, LOCAL)

    def test_answer_xp_and_due(self):
        self.unlock()
        session = self.as_script(self.Session)._start(self.as_script(self.student), self.deck, kind="unit", unit=self.t7)
        item = session._current_item()
        session._answer(item, "999" if item.answer_mode == "keypad" else "?", first_touch_ms=900, submit_ms=1300)
        xp = self.Xp.search([("student_id", "=", self.student.id)])
        self.assertTrue(xp)
        self.assertEqual(set(xp.mapped("day")), {LOCAL})
        self.assertEqual(self.as_script(self.student)._practice_xp_today(), sum(xp.mapped("amount")))
        self.assertEqual(self.mastery(item).due_on, LOCAL, "a missed item is due again today")

    def test_quests_and_goals(self):
        self.unlock()
        Quest = self.as_script(self.Quest)
        self.assertEqual(Quest._today(self.student), LOCAL)
        quests = Quest._draw(self.student)
        self.assertTrue(quests)
        self.assertEqual(set(quests.mapped("day")), {LOCAL})
        session = self.as_script(self.Session)._start(self.as_script(self.student), self.deck, kind="unit", unit=self.t7)
        self.assertEqual(session._todays_quests(), quests)
        goal = self.env["homeschool.practice.goal"]._for(self.student, "day", LOCAL)
        new = self.as_script(goal).action_change_target(4)
        self.assertEqual(new.date_from, date(2026, 11, 19), "from the learner's tomorrow")

    def test_reward_rule_starts_today(self):
        rt = self.env["homeschool.reward.type"].create({"name": "Synthetic minutes", "unit": "min"})
        rule = self.as_script(self.env["homeschool.reward.rule"]).create(
            {"student_id": self.student.id, "goal_period": "day", "reward_type_id": rt.id, "amount": 5})
        self.assertEqual(rule.date_from, LOCAL)


class TestMigration(LearnerTodayCase):

    def migrate(self):
        path = os.path.join(os.path.dirname(__file__), "..", "migrations", "19.0.1.8.1", "post-migrate.py")
        spec = importlib.util.spec_from_file_location("hs_practice_mig_1_8_1", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.migrate(self.env.cr, "19.0.1.8.0")
        self.env.invalidate_all()

    def test_unlocked_on_and_xp_day(self):
        Access = self.env["homeschool.practice.unit.access"]
        t2 = self.deck.unit_ids.filtered(lambda u: u.sequence == 2)
        (self.t7 | self.t3 | t2).action_unlock(self.student)
        rows = Access.search([("student_id", "=", self.student.id)])
        bug, morning, parent = (rows.filtered(lambda r, u=u: r.unit_id == u) for u in (self.t7, self.t3, t2))
        self.env.flush_all()
        cr = self.env.cr
        crafted = [
            (bug, "2026-11-19 00:30:00", "2026-11-19"),      # the bug: UTC date, evening → fixed
            (morning, "2026-11-18 15:00:00", "2026-11-18"),  # same date either way → left
            (parent, "2026-11-19 00:30:00", "2026-11-17"),   # not the UTC date → left
        ]
        for row, created, unlocked in crafted:
            cr.execute("UPDATE homeschool_practice_unit_access SET create_date = %s, unlocked_on = %s WHERE id = %s",
                       (created, unlocked, row.id))
        xp_bad = self.Xp._award(self.student, 3, "answer")
        xp_ok = self.Xp._award(self.student, 2, "answer")
        self.env.flush_all()
        cr.execute("UPDATE homeschool_practice_xp SET date = %s, day = %s WHERE id = %s", (EVENING, "2026-11-19", xp_bad.id))
        cr.execute("UPDATE homeschool_practice_xp SET date = %s, day = %s WHERE id = %s",
                   ("2026-11-18 15:00:00", "2026-11-18", xp_ok.id))
        self.migrate()
        self.assertEqual(bug.unlocked_on, LOCAL)
        self.assertEqual(morning.unlocked_on, date(2026, 11, 18))
        self.assertEqual(parent.unlocked_on, date(2026, 11, 17))
        self.assertEqual(xp_bad.day, LOCAL)
        self.assertEqual(xp_ok.day, LOCAL)
        self.migrate()  # idempotent
        self.assertEqual(bug.unlocked_on, LOCAL)


@tagged("post_install", "-at_install")
class TestProgressPageLocalDate(PracticeHttpCase):

    def test_last_practised_is_the_learners_date(self):
        t7 = self.deck.unit_ids.filtered(lambda u: u.sequence == 7)
        self.env["homeschool.practice.unit.access"].search(
            [("student_id", "=", self.student.id), ("unit_id", "=", t7.id)]).unlocked_on = "2026-11-10"
        row = self.env["homeschool.practice.mastery"].search(
            [("student_id", "=", self.student.id), ("unit_id", "=", t7.id)], limit=1)
        row.last_seen = EVENING
        self.env["ir.config_parameter"].sudo().set_param("bemade_portal_kit.enabled", "1")
        self.authenticate("hs_teacher", "hs_teacher")
        res = self.url_open("/my/homeschool/%d/practice/progress" % self.student.id)
        self.assertEqual(res.status_code, 200)
        line = re.search(r'(?s)data-hs-unit="%d">.*?</tr>' % t7.id, res.text).group(0)
        self.assertIn("11/18/2026", line)
        self.assertNotIn("11/19/2026", line)
