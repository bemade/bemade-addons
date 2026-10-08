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
6. Coverage is **per family**: the shared item carries no status of its own; a
   ``homeschool.item.coverage`` row keyed (item, company) holds the family's status,
   computed status, manual override, note, date and evidence refs, computed from THAT
   family's traces and blocks by the rules of §1. A trace or block of family B never
   changes family A's coverage; the item's coverage fields, the evidenced / not started
   filters and the group-by resolve against the current company; rows exist only for the
   (item, family) pairs that hold evidence or a manual status (an item without a row is
   ``not_started``); ``coverage.csv`` is exported per family with the same columns.
"""
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

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

    # ------------------------------------------------------------------
    # 6. per family
    # ------------------------------------------------------------------
    def _trace_b(self, item, d=date(2026, 2, 2), name="B evidence"):
        env = self.env(context=dict(self.env.context, allowed_company_ids=self.company_b.ids))
        return env["homeschool.trace"].create({"name": name, "student_id": self.student_b.id, "date": d, "item_ids": [(6, 0, [item.id])]})

    def test_rows_are_lazy_and_keyed_by_family(self):
        item = self.item_fle
        Coverage = self.env["homeschool.item.coverage"]
        self.assertFalse(item.coverage_ids, "no evidence, no manual status: no row")
        self.assertFalse(item._coverage_for(self.company))
        self.assertEqual(item.coverage_status, "not_started")
        trace_b = self._trace_b(item)
        row_b = item._coverage_for(self.company_b)
        self.assertEqual(len(row_b), 1)
        self.assertEqual((row_b.item_id, row_b.company_id), (item, self.company_b))
        self.assertEqual(row_b.status, "evidenced")
        self.assertEqual(row_b.trace_ids, trace_b)
        self.assertEqual(row_b.evidence_refs, trace_b.code)
        self.assertFalse(item._coverage_for(self.company), "family A still has no row")
        # one row per (item, family)
        with self.assertRaises(Exception), mute_logger("odoo.sql_db"):
            Coverage.create({"item_id": item.id, "company_id": self.company_b.id})

    def test_family_b_evidence_never_changes_family_a(self):
        item = self.item_fle
        self.assertEqual(item.coverage_status, "not_started")
        trace_b = self._trace_b(item)
        # the current company is A: nothing moved
        self.assertEqual(item.coverage_status, "not_started")
        self.assertEqual(item.coverage_computed, "not_started")
        self.assertEqual((item.trace_count, item.block_count), (0, 0))
        self.assertFalse(item.last_evidence_date)
        # seen from B: evidenced, with B's trace behind it
        item_b = item.with_company(self.company_b)
        self.assertEqual(item_b.coverage_status, "evidenced")
        self.assertEqual(item_b.trace_count, 1)
        self.assertEqual(item_b.last_evidence_date, trace_b.date)
        # A's own evidence does not leak into B either
        today = fields.Date.context_today(self.Day)
        block_a = self.make_block(self.make_day(today), "A block", 45, 1, item_ids=[(6, 0, [item.id])], status="done")
        self.assertEqual(item.coverage_status, "in_progress")
        self.assertEqual(item.block_count, 1)
        self.assertEqual(item_b.coverage_status, "evidenced")
        self.assertEqual(item_b.block_count, 0)
        # and B's row is unaffected by changes to A's block
        block_a.status = "planned"
        self.assertEqual(item.coverage_status, "planned")
        self.assertEqual(item_b.coverage_status, "evidenced")
        trace_b.unlink()
        self.assertEqual(item_b.coverage_status, "not_started")
        self.assertEqual(item.coverage_status, "planned")

    def test_manual_status_is_per_family(self):
        item = self.item_math
        item.coverage_override = "planned"
        item.coverage_note = "A note"
        row_a = item._coverage_for(self.company)
        self.assertEqual((row_a.override, row_a.note), ("planned", "A note"))
        self.assertEqual(item.coverage_status, "planned")
        item_b = item.with_company(self.company_b)
        self.assertFalse(item_b.coverage_override)
        self.assertFalse(item_b.coverage_note)
        self.assertEqual(item_b.coverage_status, "not_started")
        item_b.coverage_override = "evidenced"
        self.assertEqual(item_b.coverage_status, "evidenced")
        self.assertEqual(item.coverage_status, "planned")
        self.assertEqual(len(item.coverage_ids), 2)

    def test_filters_and_group_by_resolve_against_the_current_company(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        imp.import_traces(self.repo, self.student)
        math = self.Item._by_code("MATH-MES-G.1")
        st = self.Item._by_code("ST-MAT-D.4.a")
        self._trace_b(st)
        pda = [("kind", "=", "pda"), ("source_ref", "!=", False)]
        Item_b = self.Item.with_company(self.company_b)
        # A: MATH, US and FLE-...E.2.a.i evidenced; ST and the FLE section not started
        self.assertIn(math, self.Item.search(pda + [("coverage_status", "=", "evidenced")]))
        self.assertIn(st, self.Item.search(pda + [("coverage_status", "=", "not_started")]))
        self.assertNotIn(st, self.Item.search(pda + [("coverage_status", "=", "evidenced")]))
        self.assertEqual(self.Item.search(pda + [("coverage_status", "!=", "not_started")]),
                         self.Item.search(pda + [("coverage_status", "in", ["planned", "in_progress", "evidenced"])]))
        # B: only ST is evidenced; items without a row are not started
        self.assertEqual(Item_b.search(pda + [("coverage_status", "=", "evidenced")]), st.with_company(self.company_b))
        self.assertIn(math, Item_b.search(pda + [("coverage_status", "=", "not_started")]))
        self.assertEqual(Item_b.search_count(pda + [("coverage_status", "=", "not_started")]), 4)
        self.assertEqual(Item_b.search_count(pda + [("coverage_status", "!=", "evidenced")]), 4)
        # group by
        def table(model):
            return {(s.code, st_): n for s, st_, n in model._read_group(pda, ["subject_id", "coverage_status"], ["__count"])}
        table_a, table_b = table(self.Item), table(Item_b)
        self.assertEqual(table_a[("MATH", "evidenced")], 1)
        self.assertEqual(table_a[("ST", "not_started")], 1)
        self.assertEqual(table_b[("ST", "evidenced")], 1)
        self.assertEqual(table_b[("MATH", "not_started")], 1)
        self.assertEqual(table_b.get(("US", "evidenced")), None)
        self.assertEqual(sum(table_b.values()), 5)

    def test_coverage_csv_is_per_family(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        imp.import_coverage(self.repo)
        imp.import_traces(self.repo, self.student)
        Exporter = self.env["homeschool.exporter"]
        before = Exporter.export_coverage(self.student)
        # family B: a trace on MATH and a manual status on ST — A's file is unchanged
        math = self.Item._by_code("MATH-MES-G.1")
        st = self.Item._by_code("ST-MAT-D.4.a")
        trace_b = self._trace_b(math)
        st.with_company(self.company_b).write({"coverage_override": "planned", "coverage_note": "B plans it", "coverage_date": date(2026, 2, 1)})
        self.assertEqual(Exporter.export_coverage(self.student), before)
        self.assertEqual(Exporter.with_user(self.manager_user()).export_texts(self.student.id, files=["tracking/coverage.csv"])["tracking/coverage.csv"], before)
        rows_b = Exporter.export_coverage(self.student_b).splitlines()
        self.assertEqual(rows_b[0], "pda_id,status,evidence_refs,date_updated,notes")
        self.assertEqual([r.split(",")[0] for r in rows_b], [r.split(",")[0] for r in before.splitlines()], "same items, same order")
        self.assertIn("MATH-MES-G.1,evidenced,%s,," % trace_b.code, rows_b)
        self.assertIn("ST-MAT-D.4.a,planned,,2026-02-01,B plans it", rows_b)
        self.assertIn("US-C1-1820,not_started,,,", rows_b, "A's manual status on US stays in A")
        self.assertNotIn("TR-2026-01-05", "\n".join(rows_b), "A's traces never appear in B's file")
        # importing B's own coverage.csv writes B's rows only
        n_rows_a = len(self.env["homeschool.item.coverage"].search([("company_id", "=", self.company.id)]))
        imp.with_company(self.company_b).import_coverage(self.repo, company=self.company_b)
        self.assertEqual(st.with_company(self.company_b).coverage_override, False, "the CSV says not_started")
        self.assertEqual(self.Item._by_code("US-C1-1820").with_company(self.company_b).coverage_note, "Kingston trip")
        self.assertEqual(len(self.env["homeschool.item.coverage"].search([("company_id", "=", self.company.id)])), n_rows_a)
        self.assertEqual(Exporter.export_coverage(self.student), before)

    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_coverage_rows_follow_the_company_rules(self):
        item = self.item_fle
        self._trace_b(item)
        today = fields.Date.context_today(self.Day)
        self.make_block(self.make_day(today), "A block", 45, 1, item_ids=[(6, 0, [item.id])])
        row_a, row_b = item._coverage_for(self.company), item._coverage_for(self.company_b)
        manager_b = self.manager_user(self.company_b, login="hs_manager_b")
        Coverage = self.env["homeschool.item.coverage"].with_user(manager_b)
        self.assertEqual(Coverage.search([("item_id", "=", item.id)]), row_b.with_user(manager_b))
        with self.assertRaises(AccessError):
            row_a.with_user(manager_b).read(["status"])
        self.assertEqual(item.with_user(manager_b).coverage_status, "evidenced", "the manager's company is B")
        self.assertEqual(item.with_user(manager_b).coverage_ids, row_b.with_user(manager_b))
