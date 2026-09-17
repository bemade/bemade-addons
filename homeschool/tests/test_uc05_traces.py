# -*- coding: utf-8 -*-
"""UC-05 — Traces: dated artifacts for the portfolio, with a diffusion level.

Acceptance criteria
-------------------
1. ``homeschool.trace`` has ``code`` (``TR-YYYY-MM-DD-a``, generated: next letter for
   the date, unique), ``date``, ``name``, ``subject_ids``, ``item_ids``, attachments,
   ``diffusion`` (internal | institutional), ``note``, ``student_comment`` (the child's
   own words — portfolio content, never journal), ``block_id``, ``project_id``,
   ``submitted_by`` (parent | student).
2. An **institutional** trace cannot reference an internal-only item (kind =
   internal) — ValidationError, mirroring ``report.py check``.
3. Importing ``tracking/traces.csv`` preserves ``trace_id`` as code and external id,
   splits ``matieres`` and ``pda_ids`` on ``;``, attaches ``artifact_path`` when the
   file exists in the repository path given to the importer.
4. A trace created from a block inherits the block's date, subject and items as
   defaults.
5. Traces are ``mail.thread``: attachments and comments are tracked.
"""
from datetime import date

from odoo.exceptions import ValidationError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestTraces(HomeschoolCase):
    def test_code_generation(self):
        a = self.Trace.create({"name": "One", "date": date(2026, 2, 3), "student_id": self.student.id})
        b = self.Trace.create({"name": "Two", "date": date(2026, 2, 3), "student_id": self.student.id})
        c = self.Trace.create({"name": "Three", "date": date(2026, 2, 4), "student_id": self.student.id})
        self.assertEqual((a.code, b.code, c.code), ("TR-2026-02-03-a", "TR-2026-02-03-b", "TR-2026-02-04-a"))
        with mute_logger("odoo.sql_db"), self.assertRaises(Exception):
            self.Trace.create({"name": "Dup", "date": date(2026, 2, 3), "student_id": self.student.id, "code": "TR-2026-02-03-a"})

    @mute_logger("odoo.sql_db")
    def test_institutional_refuses_internal_items(self):
        with self.assertRaises(ValidationError):
            self.Trace.create({"name": "X", "student_id": self.student.id, "diffusion": "institutional",
                               "item_ids": [(6, 0, [self.item_fle.id, self.item_internal.id])]})
        ok = self.Trace.create({"name": "Y", "student_id": self.student.id, "diffusion": "internal",
                                "item_ids": [(6, 0, [self.item_internal.id])]})
        with self.assertRaises(ValidationError):
            ok.diffusion = "institutional"

    def test_traces_csv_import(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        log = imp.import_traces(self.repo, self.student)
        a = self.Trace.search([("code", "=", "TR-2026-01-05-a")])
        self.assertEqual(a, self.env.ref("homeschool.trace_TR_2026_01_05_a"))
        self.assertEqual(a.date, date(2026, 1, 5))
        self.assertEqual(a.subject_ids, self.math)
        self.assertEqual(sorted(a.item_ids.mapped("code")), ["FLE-E-SYN-C-E.2.a.i", "MATH-MES-G.1"])
        self.assertEqual(a.diffusion, "internal")
        self.assertEqual(a.note, "note one")
        self.assertEqual(a.attachment_ids.mapped("name"), ["TR-2026-01-05-a.pdf"])
        b = self.Trace.search([("code", "=", "TR-2026-01-05-b")])
        self.assertEqual(b.diffusion, "institutional")
        self.assertEqual(b.item_ids.mapped("code"), ["US-C1-1820"])
        self.assertFalse(b.attachment_ids)
        imp.import_traces(self.repo, self.student)
        self.assertEqual(self.Trace.search_count([("code", "like", "TR-2026-01-05%")]), 2)
        self.assertEqual(len(a.attachment_ids), 1, "re-import does not duplicate attachments")

    def test_defaults_from_block(self):
        day = self.make_day(date(2026, 1, 20))
        block = self.make_block(day, "Segment 1", 45, 1, subject_id=self.fle.id, item_ids=[(6, 0, [self.item_fle.id])])
        trace = self.Trace.with_context(default_block_id=block.id).create({"name": "From block"})
        self.assertEqual(trace.date, date(2026, 1, 20))
        self.assertEqual(trace.student_id, self.student)
        self.assertEqual(trace.subject_ids, self.fle)
        self.assertEqual(trace.item_ids, self.item_fle)
        self.assertEqual(trace.block_id, block)
        self.assertEqual(trace.code, "TR-2026-01-20-a")
        self.assertIn(trace, block.trace_ids)
        self.assertTrue(trace.message_ids is not None, "mail.thread")
