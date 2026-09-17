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
from .common import HomeschoolCase


class TestIndicatorsReviews(HomeschoolCase):
    def test_definitions_import(self):
        self.skipTest("pending — TDD")

    def test_skipped_is_absent_not_zero(self):
        self.skipTest("pending — TDD")

    def test_r1_adulte_computed_weekly(self):
        self.skipTest("pending — TDD")

    def test_weekly_review_lists_missing(self):
        self.skipTest("pending — TDD")
