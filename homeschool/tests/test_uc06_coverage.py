# -*- coding: utf-8 -*-
"""UC-06 — Coverage of the curriculum is computed, with the evidence one click away.

Acceptance criteria
-------------------
1. ``homeschool.item.coverage_status`` is computed: ``not_started`` (no block, no
   trace), ``planned`` (targeted by a future block), ``in_progress`` (targeted by a
   done or partial block, no trace), ``evidenced`` (≥ 1 trace); an explicit manual
   override field exists for the three items currently ``planned`` by hand.
2. ``trace_count``, ``block_count``, ``last_evidence_date`` are computed and stored.
3. Coverage per subject and per priority is a ``read_group`` over items (count by
   status), matching ``report.py coverage`` on the imported data set.
4. ``tracking/coverage.csv`` imports as the initial override/status snapshot and
   exports back with the same columns (pda_id, status, evidence_refs = trace codes,
   date_updated, notes).
5. Established / in-motion / open stays visible: the item form shows its source ref
   and every trace and block behind the status; no status is shown without them.
"""
from .common import HomeschoolCase


class TestCoverage(HomeschoolCase):
    def test_status_transitions(self):
        self.skipTest("pending — TDD")

    def test_counts_and_last_evidence(self):
        self.skipTest("pending — TDD")

    def test_read_group_by_subject_matches_report(self):
        self.skipTest("pending — TDD")

    def test_coverage_csv_roundtrip(self):
        self.skipTest("pending — TDD")
