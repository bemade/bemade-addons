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
   splits ``matieres`` and ``pda_ids`` on ``;`` (``,`` is tolerated), attaches
   ``artifact_path`` when the file exists in the repository path given to the importer.
   An unknown ``matieres`` key is reported in the import log and the trace is imported
   without that subject; the importer never creates a subject from ``traces.csv``.
4. A trace created from a block inherits the block's date, subject and items as
   defaults.
5. Traces are ``mail.thread``: attachments and comments are tracked.
6. A file linked to a trace or a material while it still has no record (``res_id = 0``,
   uploaded before the record was saved) is **stamped** with the record's model and id
   on create and on write (``attachment_ids``; the material's ``pdf_attachment_id`` too);
   the 19.0.5.0.0 migration stamps the rows already there, and is idempotent.
"""
import importlib.util
import os
import shutil
import tempfile
from datetime import date

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.modules.module import get_module_path
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

    def test_traces_csv_comma_matieres_and_unknown_subject(self):
        Subject = self.env["homeschool.subject"]
        n_subjects = Subject.with_context(active_test=False).search_count([])
        root = tempfile.mkdtemp(prefix="homeschool-traces-")
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        os.makedirs(os.path.join(root, "tracking"))
        with open(os.path.join(root, "tracking", "traces.csv"), "w", encoding="utf-8") as fh:
            fh.write(
                "trace_id,date,title,matieres,pda_ids,artifact_path,diffusion,notes\n"
                'TR-2026-02-02-a,2026-02-02,Comma trace,"FLE,MATH",,,INTERNAL,\n'
                "TR-2026-02-02-b,2026-02-02,Unknown trace,ZZZ;US,,,INTERNAL,\n"
            )
        log = self.env["homeschool.importer"].import_traces(root, self.student)
        a = self.Trace.search([("code", "=", "TR-2026-02-02-a")])
        self.assertEqual(a.subject_ids, self.fle | self.math, "a comma-separated matieres resolves both subjects")
        b = self.Trace.search([("code", "=", "TR-2026-02-02-b")])
        self.assertEqual(len(b), 1, "the row is imported")
        self.assertEqual(b.subject_ids, self.us, "…with the subjects it could resolve")
        self.assertIn("traces.csv TR-2026-02-02-b: unknown subject 'ZZZ'", log)
        self.assertEqual(Subject.with_context(active_test=False).search_count([]), n_subjects,
                         "traces.csv never creates a subject")
        self.assertFalse(Subject.with_context(active_test=False).search([("code", "in", ["ZZZ", "FLE,MATH"])]))

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

    # ------------------------------------------------------------------
    # 6. files uploaded before the record: stamped on link
    # ------------------------------------------------------------------
    def _orphan(self, name, res_model="homeschool.trace"):
        """An attachment as the binary widgets create it before the record is saved."""
        return self.env["ir.attachment"].create({"name": name, "raw": b"%PDF-1.4 " + name.encode(), "res_model": res_model, "res_id": 0})

    def test_orphan_attachments_stamped_on_trace_create_and_write(self):
        a = self._orphan("a.pdf")
        b = self._orphan("b.pdf", res_model=False)
        trace = self.Trace.create({"name": "Stamped", "student_id": self.student.id, "attachment_ids": [fields.Command.set([a.id])]})
        self.assertEqual((a.res_model, a.res_id), ("homeschool.trace", trace.id))
        trace.write({"attachment_ids": [fields.Command.link(b.id)]})
        self.assertEqual((b.res_model, b.res_id), ("homeschool.trace", trace.id))
        # a file that already belongs to another record is left alone
        other = self.Trace.create({"name": "Other", "student_id": self.student.id})
        theirs = self.env["ir.attachment"].create({"name": "theirs.pdf", "raw": b"x", "res_model": "homeschool.trace", "res_id": other.id})
        trace.write({"attachment_ids": [fields.Command.link(theirs.id)]})
        self.assertEqual((theirs.res_model, theirs.res_id), ("homeschool.trace", other.id))
        # a write without attachment_ids changes nothing
        c = self._orphan("c.pdf")
        trace.write({"name": "Renamed"})
        self.assertEqual(c.res_id, 0)

    def test_orphan_attachments_stamped_on_material(self):
        Material = self.env["homeschool.material"]
        a = self._orphan("fiche.pdf", res_model="homeschool.material")
        pdf = self._orphan("main.pdf", res_model=False)
        material = Material.create({"name": "Fiche", "attachment_ids": [fields.Command.set([a.id])], "pdf_attachment_id": pdf.id})
        self.assertEqual((a.res_model, a.res_id), ("homeschool.material", material.id))
        self.assertEqual((pdf.res_model, pdf.res_id), ("homeschool.material", material.id))
        b = self._orphan("later.pdf", res_model="homeschool.material")
        material.write({"pdf_attachment_id": b.id})
        self.assertEqual((b.res_model, b.res_id), ("homeschool.material", material.id))

    def test_migration_stamps_existing_rows(self):
        path = os.path.join(get_module_path("homeschool"), "migrations", "19.0.5.0.0", "post-migrate.py")
        spec = importlib.util.spec_from_file_location("homeschool_post_migrate_19_0_5_0_0", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        trace = self.Trace.create({"name": "Old", "student_id": self.student.id})
        material = self.env["homeschool.material"].create({"name": "Old fiche"})
        a, b, pdf = self._orphan("a.pdf"), self._orphan("b.pdf", res_model="homeschool.material"), self._orphan("pdf.pdf", res_model=False)
        # linked before 19.0.5.0.0: straight into the relation tables, no stamping
        self.env.cr.execute("INSERT INTO homeschool_trace_attachment_rel (trace_id, attachment_id) VALUES (%s, %s)", (trace.id, a.id))
        self.env.cr.execute("INSERT INTO homeschool_material_attachment_rel (material_id, attachment_id) VALUES (%s, %s)", (material.id, b.id))
        self.env.cr.execute("UPDATE homeschool_material SET pdf_attachment_id = %s WHERE id = %s", (pdf.id, material.id))
        untouched = self.env["ir.attachment"].create({"name": "mine.pdf", "raw": b"x", "res_model": "homeschool.trace", "res_id": trace.id})
        self.env.cr.execute("INSERT INTO homeschool_trace_attachment_rel (trace_id, attachment_id) VALUES (%s, %s)", (trace.id, untouched.id))
        self.env.invalidate_all()
        self.assertEqual(migration.stamp_orphan_attachments(self.env.cr), 3)
        self.env.invalidate_all()
        self.assertEqual((a.res_model, a.res_id), ("homeschool.trace", trace.id))
        self.assertEqual((b.res_model, b.res_id), ("homeschool.material", material.id))
        self.assertEqual((pdf.res_model, pdf.res_id), ("homeschool.material", material.id))
        self.assertEqual((untouched.res_model, untouched.res_id), ("homeschool.trace", trace.id))
        # idempotent
        self.assertEqual(migration.stamp_orphan_attachments(self.env.cr), 0)
        migration.migrate(self.env.cr, "19.0.4.0.0")
        self.assertEqual(migration.stamp_orphan_attachments(self.env.cr), 0)
