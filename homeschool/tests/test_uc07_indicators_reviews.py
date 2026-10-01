# -*- coding: utf-8 -*-
"""UC-07 — Indicators and reviews: series without invented zeros.

Acceptance criteria
-------------------
1. ``homeschool.indicator`` = definition: ``code`` (R1-ADULTE, K1-ENGAGE…), ``porte``,
   ``name``, ``unit``, ``period`` (weekly | daily | periodic), ``direction`` (up | down),
   ``threshold`` (text), ``source``, ``note``; imported from
   ``indicateurs-definitions.csv`` with codes as external ids.
2. ``homeschool.indicator.value``: indicator, date (or ISO week), ``value`` (float,
   nullable), ``note``. A skipped indicator has **no row**, never a zero.
3. ``R1-ADULTE`` is **computed** per ISO week from block actuals (hours); recording it
   as a value is offered, not automatic (the series exists when the parent says so).
4. ``homeschool.review``: kind (weekly | six_weeks | january | june), week/date, the
   three Sunday answers (dose kept? visible cap respected? week recorded as it was?),
   missing indicators listed, days without a journal entry listed, free notes.
5. The weekly review lists which weekly indicators have no value for the week
   (replaces ``report.py review``).
"""
from datetime import date, timedelta

from odoo import fields

from .common import HomeschoolCase


class TestIndicatorsReviews(HomeschoolCase):
    def _import(self):
        return self.env["homeschool.importer"].import_indicators(self.repo, self.student)

    def test_definitions_import(self):
        self._import()
        r1 = self.env.ref("homeschool.indicator_R1_ADULTE")
        self.assertEqual(r1.code, "R1-ADULTE")
        self.assertEqual(r1.porte, "R1 / D5")
        self.assertEqual(r1.unit, "h/sem")
        self.assertEqual(r1.period, "weekly")
        self.assertEqual(r1.direction, "down")
        self.assertEqual(r1.threshold, "-25 % à 6 mois")
        self.assertTrue(r1.computed)
        k1 = self.env["homeschool.indicator"]._by_code("K1-ENGAGE")
        self.assertEqual(k1.direction, "up")
        self.assertFalse(k1.computed)
        self._import()
        self.assertEqual(self.env["homeschool.indicator"].search_count([("code", "in", ["R1-ADULTE", "R3-CONFLITS", "K1-ENGAGE"])]), 3)

    def test_skipped_is_absent_not_zero(self):
        self._import()
        Value = self.env["homeschool.indicator.value"]
        conflicts = Value.search([("code", "=", "R3-CONFLITS")])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual((conflicts.date, conflicts.value, conflicts.note), (date(2026, 1, 9), 1.0, "one event"))
        self.assertEqual(conflicts.iso_week, "2026-W02")
        self.assertFalse(Value.search([("code", "=", "K1-ENGAGE")]), "never recorded = no row")
        missing = self.env["homeschool.indicator"].missing_for_week(date(2026, 1, 9))
        self.assertEqual(sorted(missing.mapped("code")), ["K1-ENGAGE"], "R1-ADULTE is computed, R3 has a value")

    def test_r1_adulte_computed_weekly(self):
        self._import()
        monday = date(2026, 1, 12)
        d1 = self.make_day(monday)
        self.make_block(d1, "A", 45, 1, minutes_total=45, minutes_adult_present=45)
        self.make_block(d1, "B", 45, 2, minutes_total=45, minutes_adult_present=15)
        Indicator = self.env["homeschool.indicator"]
        self.assertAlmostEqual(Indicator.adult_hours_for_week(self.student, monday), 1.0)
        self.assertFalse(self.env["homeschool.indicator.value"].search([("code", "=", "R1-ADULTE")]), "not automatic")
        review = self.env["homeschool.review"].create({"student_id": self.student.id, "date": monday + timedelta(days=6)})
        self.assertAlmostEqual(review.adult_hours, 1.0)
        review.action_record_adult_hours()
        value = self.env["homeschool.indicator.value"].search([("code", "=", "R1-ADULTE")])
        self.assertEqual(len(value), 1)
        self.assertAlmostEqual(value.value, 1.0)
        self.assertEqual(value.iso_week, "2026-W03")

    def test_weekly_review_lists_missing(self):
        self._import()
        sunday = date(2026, 1, 11)
        review = self.env["homeschool.review"].create({"student_id": self.student.id, "date": sunday, "kind": "weekly"})
        self.assertEqual(review.iso_week, "2026-W02")
        self.assertEqual(review.name, "Weekly (Sunday) — 2026-W02")
        self.assertEqual(review.missing_indicator_ids.mapped("code"), ["K1-ENGAGE"])
        # days without a journal entry: Mon-Fri of the week, none has an entry yet
        self.assertEqual(review.days_without_journal, "2026-01-05, 2026-01-06, 2026-01-07, 2026-01-08, 2026-01-09")
        day = self.make_day(date(2026, 1, 5))
        self.env["homeschool.journal"].create({"day_id": day.id, "went_well": "ok"})
        self.make_day(date(2026, 1, 7), is_off=True)
        review.invalidate_recordset(["days_without_journal"])
        self.assertEqual(review.days_without_journal, "2026-01-06, 2026-01-08, 2026-01-09")
