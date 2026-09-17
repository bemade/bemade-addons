# -*- coding: utf-8 -*-
"""UC-06 — Coverage of the curriculum is computed, with the evidence one click away.

Acceptance criteria
-------------------
1. ``homeschool.item.coverage_status`` is computed: ``not_started`` (no block, no
   trace), ``planned`` (targeted by a future block), ``in_progress`` (targeted by a
   done or partial block, no trace), ``evidenced`` (≥ 1 trace); an explicit manual
   override field exists for the items currently ``planned`` by hand.
2. ``trace_count``, ``block_count``, ``last_evidence_date`` are computed and stored.
3. Coverage per subject and per priority is a ``read_group`` over items (count by
   status), matching ``report.py coverage`` on the imported data set.
4. ``tracking/coverage.csv`` imports as the initial override/status snapshot and
   exports back with the same columns (pda_id, status, evidence_refs = trace codes,
   date_updated, notes).
5. Established / in-motion / open stays visible: the item form shows its source ref
   and every trace and block behind the status; no status is shown without them.
"""
from datetime import date, timedelta

from odoo import fields

from .common import HomeschoolCase


class TestCoverage(HomeschoolCase):
    def test_status_transitions(self):
        item = self.item_fle
        self.assertEqual(item.coverage_status, "not_started")
        today = fields.Date.context_today(self.Day)
        day = self.make_day(today + timedelta(days=7))
        block = self.make_block(day, "Future", 45, 1, item_ids=[(6, 0, [item.id])])
        self.assertEqual(item.coverage_status, "planned")
        block.status = "done"
        self.assertEqual(item.coverage_status, "in_progress")
        trace = self.Trace.create({"name": "Evidence", "student_id": self.student.id, "date": today, "item_ids": [(6, 0, [item.id])]})
        self.assertEqual(item.coverage_status, "evidenced")
        item.coverage_override = "planned"
        self.assertEqual(item.coverage_status, "planned", "the manual override wins")
        self.assertEqual(item.coverage_computed, "evidenced", "but the computed truth stays visible")
        trace.unlink()
        item.coverage_override = False
        self.assertEqual(item.coverage_status, "in_progress")

    def test_counts_and_last_evidence(self):
        item = self.item_math
        d1, d2 = date(2026, 1, 12), date(2026, 1, 19)
        b = self.make_block(self.make_day(d1), "B", 45, 1, item_ids=[(6, 0, [item.id])], status="done")
        self.Trace.create({"name": "T1", "student_id": self.student.id, "date": d2, "item_ids": [(6, 0, [item.id])]})
        self.assertEqual((item.trace_count, item.block_count), (1, 1))
        self.assertEqual(item.last_evidence_date, d2)
        b.day_id.date = date(2026, 1, 26)
        self.assertEqual(item.last_evidence_date, date(2026, 1, 26))

    def test_read_group_by_subject_matches_report(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        imp.import_traces(self.repo, self.student)
        groups = self.Item._read_group([("kind", "=", "pda"), ("source_ref", "!=", False)], ["subject_id", "coverage_status"], ["__count"])
        table = {(s.code, st): n for s, st, n in groups}
        # report.py coverage on the fixture: FLE 1 evidenced (E.2.a.i) + 1 not started (section),
        # MATH 1 evidenced, US 1 evidenced, ST 1 not started
        self.assertEqual(table.get(("FLE", "evidenced")), 1, table)
        self.assertEqual(table[("FLE", "not_started")], 1)
        self.assertEqual(table[("MATH", "evidenced")], 1)
        self.assertEqual(table[("US", "evidenced")], 1)
        self.assertEqual(table.get(("ST", "not_started")), 1, table)

    def test_coverage_csv_roundtrip(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        log = imp.import_coverage(self.repo)
        us = self.Item._by_code("US-C1-1820")
        self.assertEqual(us.coverage_status, "planned")
        self.assertEqual(us.coverage_override, "planned")
        self.assertEqual(us.coverage_note, "Kingston trip")
        self.assertEqual(us.coverage_date, date(2026, 1, 1))
        fle = self.Item._by_code("FLE-E-SYN-C-E")
        self.assertFalse(fle.coverage_override, "not_started is the default, not an override")
        out = self.env["homeschool.exporter"].export_coverage(self.student)
        header, *rows = out.splitlines()
        self.assertEqual(header, "pda_id,status,evidence_refs,date_updated,notes")
        row = next(r for r in rows if r.startswith("US-C1-1820,"))
        self.assertEqual(row, "US-C1-1820,planned,,2026-01-01,Kingston trip")
