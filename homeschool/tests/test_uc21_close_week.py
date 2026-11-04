# -*- coding: utf-8 -*-
"""UC-21 — « Fermer la semaine »: every weekly indicator of the week on one screen, then
the Sunday questions and the week's summary.

Acceptance criteria
-------------------
1. Default week: on a Monday–Thursday it is the **previous** ISO week; on a Friday,
   Saturday or Sunday it is the current one.
2. Step 1 lists the active, non-computed **weekly** indicators of the student's family
   except ``R3-PARENTS`` (computed from D and M), in ``csv_sequence`` order. Non-computed
   **monthly** indicators appear (marked « monthly ») only when the week ends a month (its
   Sunday is in the month's last 7 days) or when the calendar month of that Sunday has no
   value yet.
3. A blank line writes no row; ``0`` writes a 0; ``2,5`` and ``2.5`` write 2.5; ``abc``
   raises a ``UserError`` naming the indicator's code (and nothing is written).
4. A value already recorded for the indicator, student and ISO week is pre-loaded;
   editing it updates that row in place (no duplicate — the unique constraint holds);
   clearing it deletes the row.
5. ``R3-PARENTS`` = the mean of ``R3-PARENTS-D`` and ``R3-PARENTS-M`` (2 decimals, note
   « moyenne D/M (calculé) ») only when both have a value this week; when one is blank,
   the row the wizard computed earlier is removed — a row entered by hand is never deleted.
6. ``R1-ADULTE`` is recorded (or updated) for the week on **Next**, from the blocks'
   adult-present minutes (the logic shared with the review's button).
7. Step 2 reuses the existing review of that student and ISO week whatever its kind,
   otherwise **Finish** creates a weekly one dated the Sunday; the answers (dose, soft cap,
   adjustment, notes) are saved on it. The dropped question (``answer_recorded``) is not
   asked and no longer on the review form.
8. The alert shows when this week's ``R3-PARENTS`` and the previous ISO week's are both
   below 3, and not otherwise.
9. Step 1's context lists the week's journal indicator notes, one « date : text » line per
   day, empty days skipped.
10. Entry points: Track › Close the week (the server action: the family's only student, the
    default week; several students → a first screen to pick the student and the week) and
    the review form's header button (that review's week and student). Managers only.
11. fr_CA: the new labels, the menu, the « monthly » marker and the alert are translated
    (and the ``.po`` export has a msgstr for each — checked at build time).

Every record is keyed on ``student_id``: a second student's values never show.
"""
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase

# 2026-W03: Monday 12 → Sunday 18 January 2026 (not a month-end week)
MON = date(2026, 1, 12)
SUN = date(2026, 1, 18)
COMPUTED_NOTE = "moyenne D/M (calculé)"


class TestCloseWeek(HomeschoolCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["homeschool.close.week.wizard"]
        cls.Indicator = cls.env["homeschool.indicator"]
        cls.Value = cls.env["homeschool.indicator.value"]
        cls.Review = cls.env["homeschool.review"]

        def ind(code, seq, period="weekly", **vals):
            return cls.Indicator.create(dict(code=code, name="Name %s" % code, csv_sequence=seq, period=period,
                                             unit="n/wk", threshold="≤ 1", **vals))
        cls.r1 = ind("R1-ADULTE", 1, computed=True)
        cls.conflicts = ind("T-CONFLICTS", 5)
        cls.engage = ind("T-ENGAGE", 10)
        cls.r3d = ind("R3-PARENTS-D", 20)
        cls.r3m = ind("R3-PARENTS-M", 21)
        cls.r3 = ind("R3-PARENTS", 22)
        cls.monthly = ind("T-MONTHLY", 15, period="monthly")
        cls.daily = ind("T-DAILY", 3, period="daily")
        cls.inactive = ind("T-OLD", 4, active=False)
        cls.other_family = cls.Indicator.with_company(cls.company_b).create(
            {"code": "T-B-ONLY", "name": "Other family", "period": "weekly", "csv_sequence": 2})

    def _open(self, any_date=SUN, student=None):
        action = self.Wizard.action_open(student=student or self.student, any_date=any_date)
        return self.Wizard.browse(action["res_id"])

    def _line(self, wiz, code):
        return wiz.line_ids.filtered(lambda l: l.code == code)

    def _set(self, wiz, values):
        """Type ``{code: (value, note?)}`` in the line list through the form."""
        with Form(wiz) as form:
            for i, line in enumerate(wiz.line_ids):
                if line.code in values:
                    typed = values[line.code]
                    typed = typed if isinstance(typed, tuple) else (typed,)
                    with form.line_ids.edit(i) as row:
                        row.value = typed[0]
                        if len(typed) > 1:
                            row.note = typed[1]

    def _value(self, indicator, week_date=SUN, student=None):
        from odoo.addons.homeschool.models.day import iso_week_label
        return self.Value.search([("indicator_id", "=", indicator.id), ("student_id", "=", (student or self.student).id),
                                  ("iso_week", "=", iso_week_label(week_date))])

    def _add(self, indicator, d, value, note=False, student=None):
        return self.Value.create({"indicator_id": indicator.id, "student_id": (student or self.student).id,
                                  "date": d, "value": value, "note": note})

    # ------------------------------------------------------------------
    # 1. default week
    # ------------------------------------------------------------------
    def test_01_default_week(self):
        self.assertEqual(self.Wizard._default_week_date(date(2026, 1, 21)), date(2026, 1, 14), "Wednesday → last week")
        self.assertEqual(self.Wizard._default_week_date(date(2026, 1, 19)), date(2026, 1, 12), "Monday → last week")
        for d in (date(2026, 1, 16), date(2026, 1, 17), date(2026, 1, 18)):
            self.assertEqual(self.Wizard._default_week_date(d), d, "Fri/Sat/Sun → this week")
        wiz = self._open(any_date=date(2026, 1, 14))
        self.assertEqual((wiz.iso_week, wiz.week_start, wiz.week_end), ("2026-W03", MON, SUN))

    # ------------------------------------------------------------------
    # 2. the lines
    # ------------------------------------------------------------------
    def test_02_lines_and_monthly(self):
        wiz = self._open()
        self.assertEqual(wiz.step, "indicators")
        self.assertEqual(wiz.line_ids.mapped("code"), ["T-CONFLICTS", "T-ENGAGE", "T-MONTHLY", "R3-PARENTS-D", "R3-PARENTS-M"],
                         "weekly non-computed, active, own family, minus R3-PARENTS, csv order; monthly: January has no value")
        monthly = self._line(wiz, "T-MONTHLY")
        self.assertTrue(monthly.is_monthly)
        self.assertEqual(monthly.marker, "monthly")
        self.assertFalse(self._line(wiz, "T-ENGAGE").marker)
        engage = self._line(wiz, "T-ENGAGE")
        self.assertEqual((engage.name, engage.unit, engage.threshold), ("Name T-ENGAGE", "n/wk", "≤ 1"))
        # January now has a monthly value: hidden on a mid-month week, shown on the month-end week
        self._add(self.monthly, date(2026, 1, 4), 3)
        self.assertNotIn("T-MONTHLY", self._open().line_ids.mapped("code"))
        self.assertIn("T-MONTHLY", self._open(any_date=date(2026, 1, 25)).line_ids.mapped("code"), "W04 ends January")
        # last value before the week, with its date
        self._add(self.engage, date(2026, 1, 11), 2)
        self.assertEqual(self._line(self._open(), "T-ENGAGE").last_value_label, "2 (2026-01-11)")

    # ------------------------------------------------------------------
    # 3. parsing: blank, zero, comma, garbage
    # ------------------------------------------------------------------
    def test_03_blank_zero_comma_and_garbage(self):
        wiz = self._open()
        self._set(wiz, {"T-CONFLICTS": "0", "T-ENGAGE": "2,5", "T-MONTHLY": " 1.5 "})
        wiz.action_next()
        self.assertEqual(self._value(self.conflicts).value, 0.0, "a typed 0 is a value")
        self.assertEqual(self._value(self.engage).value, 2.5)
        self.assertEqual(self._value(self.engage).date, SUN, "new rows are dated the Sunday")
        self.assertEqual(self._value(self.monthly).value, 1.5)
        self.assertFalse(self._value(self.r3d), "blank → no row")
        wiz2 = self._open()
        self._set(wiz2, {"R3-PARENTS-D": "4", "T-ENGAGE": "abc"})
        with self.assertRaisesRegex(UserError, "T-ENGAGE"):
            wiz2.action_next()
        self.assertFalse(self._value(self.r3d), "nothing written when a line is refused")

    # ------------------------------------------------------------------
    # 4. pre-load, update in place, clear deletes
    # ------------------------------------------------------------------
    def test_04_preload_update_clear(self):
        existing = self._add(self.engage, date(2026, 1, 16), 3, note="friday")
        wiz = self._open()
        line = self._line(wiz, "T-ENGAGE")
        self.assertEqual((line.value, line.note, line.value_id), ("3", "friday", existing))
        self._set(wiz, {"T-ENGAGE": ("4", "updated"), "T-CONFLICTS": "1"})
        wiz.action_next()
        self.assertEqual(self._value(self.engage), existing, "updated in place, no duplicate")
        self.assertEqual((existing.value, existing.note, existing.date), (4.0, "updated", date(2026, 1, 16)))
        # re-open the same week: what was written is there; clear it → the row goes
        wiz2 = self._open()
        self.assertEqual(self._line(wiz2, "T-CONFLICTS").value, "1")
        self._set(wiz2, {"T-ENGAGE": ""})
        wiz2.action_next()
        self.assertFalse(existing.exists(), "a cleared pre-loaded value deletes its row")
        self.assertEqual(self._value(self.conflicts).value, 1.0, "untouched line kept")

    # ------------------------------------------------------------------
    # 5. R3-PARENTS
    # ------------------------------------------------------------------
    def test_05_r3_parents_mean(self):
        wiz = self._open()
        self._set(wiz, {"R3-PARENTS-D": "2", "R3-PARENTS-M": "2,5"})
        wiz.action_next()
        r3 = self._value(self.r3)
        self.assertEqual((r3.value, r3.note, r3.date), (2.25, COMPUTED_NOTE, SUN))
        wiz = self._open()
        self._set(wiz, {"R3-PARENTS-M": "3,34"})
        wiz.action_next()
        self.assertEqual(self._value(self.r3), r3, "updated, not duplicated")
        self.assertEqual(r3.value, 2.67, "2 decimals")
        wiz = self._open()
        self._set(wiz, {"R3-PARENTS-M": ""})
        wiz.action_next()
        self.assertFalse(r3.exists(), "one side blank → the computed row is removed")

    def test_05_r3_parents_by_hand_is_kept(self):
        prev_sunday = SUN - timedelta(days=7)
        by_hand = self._add(self.r3, prev_sunday, 2.25, note="imported")
        wiz = self._open(any_date=prev_sunday)
        self._set(wiz, {"R3-PARENTS-D": "2"})
        wiz.action_next()
        self.assertTrue(by_hand.exists(), "a row the wizard did not compute is never deleted")
        self.assertEqual(by_hand.value, 2.25)

    # ------------------------------------------------------------------
    # 6. R1-ADULTE
    # ------------------------------------------------------------------
    def test_06_r1_adulte_on_next(self):
        day = self.make_day(MON)
        block = self.make_block(day, "A", 60, 1, minutes_total=60, minutes_adult_present=30)
        wiz = self._open()
        wiz.action_next()
        self.assertEqual(self._value(self.r1).value, 0.5)
        block.minutes_adult_present = 60
        self._open().action_next()
        self.assertEqual(len(self._value(self.r1)), 1, "updated, not duplicated")
        self.assertEqual(self._value(self.r1).value, 1.0)
        # the review's button still records it, through the same method
        review = self.Review.create({"student_id": self.student.id, "date": SUN})
        review.action_record_adult_hours()
        self.assertEqual(len(self._value(self.r1)), 1)

    # ------------------------------------------------------------------
    # 7. the review: reuse whatever its kind, otherwise create a weekly one
    # ------------------------------------------------------------------
    def test_07_review_created_with_answers(self):
        wiz = self._open()
        wiz.action_next()
        self.assertEqual(wiz.step, "review")
        self.assertFalse(wiz.review_id, "nothing created until Finish")
        with Form(wiz) as form:
            form.answer_dose = "kept"
            form.answer_cap = "yes, mostly"
            form.adjustment = "shorter mornings"
            form.notes = "a **good** week"
        action = wiz.action_finish()
        review = self.Review.browse(action["res_id"])
        self.assertEqual((action["res_model"], review.kind, review.date, review.student_id), ("homeschool.review", "weekly", SUN, self.student))
        self.assertEqual((review.answer_dose, review.answer_cap, review.adjustment, review.notes),
                         ("kept", "yes, mostly", "shorter mornings", "a **good** week"))
        self.assertNotIn('name="answer_recorded"', self.env.ref("homeschool.view_review_form").arch)
        self.assertNotIn("answer_recorded", wiz._fields)

    def test_07_review_reused_whatever_its_kind(self):
        review = self.Review.create({"student_id": self.student.id, "date": date(2026, 1, 14), "kind": "six_weeks",
                                     "answer_dose": "before"})
        self.Review.create({"student_id": self.student_b.id, "date": SUN, "company_id": self.company_b.id})
        wiz = self._open()
        wiz.action_next()
        self.assertEqual(wiz.review_id, review)
        self.assertEqual(wiz.answer_dose, "before", "pre-loaded")
        wiz.answer_dose = "after"
        wiz.action_finish()
        self.assertEqual(self.Review.search_count([("student_id", "=", self.student.id), ("iso_week", "=", "2026-W03")]), 1)
        self.assertEqual((review.kind, review.answer_dose), ("six_weeks", "after"))

    def test_07_summary(self):
        day = self.make_day(MON)
        self.make_block(day, "A", 60, 1, minutes_total=60, minutes_adult_present=45)
        wiz = self._open()
        self._set(wiz, {"T-ENGAGE": "1"})
        wiz.action_next()
        self.assertEqual(wiz.adult_hours, 0.75)
        self.assertIn("2026-01-12", wiz.days_without_journal)
        self.assertEqual(wiz.blank_codes, "T-CONFLICTS, T-MONTHLY, R3-PARENTS-D, R3-PARENTS-M")
        wiz.action_previous()
        self.assertEqual(wiz.step, "indicators")
        self.assertEqual(self._line(wiz, "T-ENGAGE").value, "1", "back on step 1: what was written")

    # ------------------------------------------------------------------
    # 8. the R3-PARENTS alert
    # ------------------------------------------------------------------
    def test_08_alert(self):
        prev = SUN - timedelta(days=7)
        self._add(self.r3, prev, 2.5, note="imported")
        wiz = self._open()
        self._set(wiz, {"R3-PARENTS-D": "2", "R3-PARENTS-M": "3"})
        wiz.action_next()
        self.assertTrue(wiz.r3_alert, "2.5 then 2.5")
        wiz.action_previous()
        self._set(wiz, {"R3-PARENTS-D": "3"})
        wiz.action_next()
        self.assertFalse(wiz.r3_alert, "this week = 3, not below")
        # previous week not below 3
        self.Value.search([("indicator_id", "=", self.r3.id), ("date", "=", prev)]).value = 3.5
        wiz.action_previous()
        self._set(wiz, {"R3-PARENTS-D": "1"})
        wiz.action_next()
        self.assertFalse(wiz.r3_alert, "previous week 3.5")
        # another student's low weeks never raise the first one's alert
        self.assertFalse(self._open(student=self.student_b).r3_alert)

    # ------------------------------------------------------------------
    # 9. journal indicator notes in the context
    # ------------------------------------------------------------------
    def test_09_journal_notes(self):
        Journal = self.env["homeschool.journal"]
        d1, d2, d3 = self.make_day(MON), self.make_day(MON + timedelta(days=1)), self.make_day(MON + timedelta(days=3))
        Journal.create({"day_id": d1.id, "indicator_notes": "one conflict"})
        Journal.create({"day_id": d2.id, "went_well": "fine"})
        Journal.create({"day_id": d3.id, "indicator_notes": "engaged twice"})
        outside = self.make_day(MON - timedelta(days=1))
        Journal.create({"day_id": outside.id, "indicator_notes": "previous week"})
        wiz = self._open()
        self.assertEqual(wiz.journal_notes, "2026-01-12 : one conflict\n2026-01-15 : engaged twice")

    # ------------------------------------------------------------------
    # 10. entry points, several students, managers only
    # ------------------------------------------------------------------
    def test_10_menu_and_review_button(self):
        self.assertTrue(self.env.ref("homeschool.menu_close_week"))
        self.assertEqual(self.env.ref("homeschool.menu_close_week").action, self.env.ref("homeschool.action_close_week_wizard"))
        action = self.Wizard.action_open()
        wiz = self.Wizard.browse(action["res_id"])
        self.assertEqual((wiz.student_id, wiz.step), (self.student, "indicators"), "the family's only student")
        expected = self.Wizard._default_week_date(date.today())
        self.assertEqual(wiz.week_start, expected - timedelta(days=expected.weekday()))
        review = self.Review.create({"student_id": self.student.id, "date": date(2026, 1, 13), "kind": "six_weeks"})
        action = review.action_open_close_week_wizard()
        wiz = self.Wizard.browse(action["res_id"])
        self.assertEqual((wiz.student_id, wiz.iso_week), (self.student, "2026-W03"))
        self.assertIn('name="action_open_close_week_wizard"', self.env.ref("homeschool.view_review_form").arch)
        with Form(review):
            pass  # the review form, header button included, still loads
        with Form(wiz):
            pass

    def test_10_several_students_pick_first(self):
        partner = self.env["res.partner"].create({"name": "Second Test Student"})
        second = self.Student.create({"partner_id": partner.id, "birthdate": "2017-05-05"})
        wiz = self.Wizard.browse(self.Wizard.action_open()["res_id"])
        self.assertEqual(wiz.step, "start")
        self.assertFalse(wiz.student_id, "never assume a single student")
        self.assertTrue(wiz.multi_student)
        with Form(wiz) as form:
            form.student_id = second
            form.date = SUN
        wiz.action_load()
        self.assertEqual((wiz.step, wiz.student_id, wiz.iso_week), ("indicators", second, "2026-W03"))
        self._add(self.engage, SUN, 4)  # the first student's value
        self.assertFalse(self._line(self._open(student=second), "T-ENGAGE").value, "keyed on student_id")

    def test_10_other_family_lines(self):
        wiz = self._open(student=self.student_b)
        self.assertEqual(wiz.line_ids.mapped("code"), ["T-B-ONLY"])

    def test_10_managers_only(self):
        plain = self.internal_user()
        with self.assertRaises(AccessError), mute_logger("odoo.addons.base.models.ir_model"):
            self.Wizard.with_user(plain).action_open(student=self.student, any_date=SUN)
        manager = self.manager_user()
        action = self.Wizard.with_user(manager).action_open(student=self.student.with_user(manager), any_date=SUN)
        self.assertTrue(action["res_id"])

    # ------------------------------------------------------------------
    # 11. fr_CA
    # ------------------------------------------------------------------
    def test_11_french(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.env["ir.module.module"]._load_module_terms(["homeschool"], ["fr_CA"])
        fr = self.env(context=dict(self.env.context, lang="fr_CA"))
        self.assertEqual(fr.ref("homeschool.menu_close_week").name, "Fermer la semaine")
        self.assertEqual(fr.ref("homeschool.action_close_week_wizard").name, "Fermer la semaine")
        Review = fr["homeschool.review"]
        self.assertEqual(Review._fields["answer_cap"]._description_string(fr), "Plafond souple — on a arrêté aux bons moments?")
        Line = fr["homeschool.close.week.wizard.line"]
        self.assertEqual(Line._fields["value"]._description_string(fr), "Valeur")
        wiz = self.Wizard.with_context(lang="fr_CA").browse(self._open().id)
        self.assertEqual(self._line(wiz, "T-MONTHLY").marker, "mensuel")
        arch = fr["homeschool.close.week.wizard"].get_views([(False, "form")])["views"]["form"]["arch"]
        self.assertIn("Deuxième semaine d'affilée sous 3", arch)
