# -*- coding: utf-8 -*-
"""UC-09 — Material catalogue and projects.

Acceptance criteria
-------------------
1. ``homeschool.material``: ``name``, ``kind`` (fiche | worksheet | poster | reading |
   exercise), PDF as attachment (``pdf_attachment_id``), ``html_source_path`` (path
   of the HTML source in the family repository), ``item_ids``, ``subject_ids``,
   ``description``, ``diffusion``; usable from blocks (``material_ids``) and from the
   day view as "material of the day" (links open the attachment).
2. Importing ``materiel/README.md``'s inventory table seeds the catalogue (name,
   files, usage) and attaches the PDFs found on disk.
3. ``homeschool.project``: ``code`` (P-3D, P-ROBOT…), ``name``, ``kind`` (project |
   mini_project), ``state`` (candidate | pilot | active | parked | done), ``season``,
   ``description``, ``carries`` (what it carries), ``item_ids``, ``block_ids``,
   ``trace_ids``, ``student_vote`` (up | down | none) and ``student_reason``;
   imported from ``plan/curriculum/projets.csv``.
4. A project's ``all_item_ids`` are the union of its own items and the items of its
   blocks and traces (computed, for the coverage view).
"""
from datetime import date

from .common import HomeschoolCase


class TestMaterialProjects(HomeschoolCase):
    def test_material_with_attachment(self):
        Material = self.env["homeschool.material"]
        att = self.env["ir.attachment"].create({"name": "fiche.pdf", "raw": b"%PDF-1.4 x", "mimetype": "application/pdf"})
        mat = Material.create({"name": "A fiche", "kind": "fiche", "pdf_attachment_id": att.id, "html_source_path": "materiel/fiches/a.html",
                               "item_ids": [(6, 0, [self.item_fle.id])], "subject_ids": [(6, 0, [self.fle.id])]})
        day = self.make_day(date(2026, 1, 20))
        block = self.make_block(day, "S1", 45, 1, material_ids=[(6, 0, [mat.id])])
        self.assertEqual(day.material_ids, mat, "material of the day comes from its blocks")
        self.assertEqual(mat.block_ids, block)
        self.assertEqual(mat.diffusion, "internal")

    def test_material_inventory_import(self):
        imp = self.env["homeschool.importer"]
        imp.import_curriculum(self.repo)
        log = imp.import_material(self.repo)
        Material = self.env["homeschool.material"]
        fiche = Material.search([("name", "=", "Test fiche")])
        self.assertEqual(fiche.kind, "fiche")
        self.assertEqual(fiche.pdf_path, "materiel/fiches/test-fiche.pdf")
        self.assertEqual(fiche.html_source_path, "materiel/fiches/test-fiche.html")
        self.assertEqual(fiche.pdf_attachment_id.name, "test-fiche.pdf")
        self.assertEqual(fiche.item_ids.mapped("code"), ["FLE-E-SYN-C-E.2.a.i"])
        self.assertEqual(fiche.subject_ids, self.fle)
        poster = Material.search([("name", "=", "Test poster")])
        self.assertEqual(poster.kind, "poster")
        self.assertFalse(poster.pdf_attachment_id, "file not on disk: no attachment, no error")
        self.assertEqual(poster.item_ids.mapped("code"), ["US-C1-1820"])
        imp.import_material(self.repo)
        self.assertEqual(Material.search_count([("name", "in", ["Test fiche", "Test poster"])]), 2, "idempotent")

    def test_project_states_and_vote(self):
        imp = self.env["homeschool.importer"]
        imp.import_projects(self.repo)
        project = self.env.ref("homeschool.project_P_TEST")
        self.assertEqual(project.name, "Test project")
        self.assertEqual(project.kind, "project")
        self.assertEqual(project.carries, "ST;MATH")
        self.assertEqual(project.description, "a project, with a comma")
        self.assertEqual(project.student_vote, "none")
        project.write({"state": "pilot", "student_vote": "up", "student_reason": "because"})
        self.assertEqual(project.state, "pilot")
        mini = self.env["homeschool.project"].create({"code": "MP-1", "name": "Mini", "kind": "mini_project"})
        self.assertEqual(mini.state, "candidate")

    def test_project_items_union(self):
        project = self.env["homeschool.project"].create({"code": "P-U", "name": "Union", "item_ids": [(6, 0, [self.item_fle.id])]})
        day = self.make_day(date(2026, 1, 21))
        self.make_block(day, "S1", 45, 1, project_id=project.id, item_ids=[(6, 0, [self.item_math.id])])
        self.Trace.create({"name": "T", "student_id": self.student.id, "project_id": project.id, "item_ids": [(6, 0, [self.item_internal.id])]})
        self.assertEqual(project.all_item_ids, self.item_fle | self.item_math | self.item_internal)
        self.assertEqual(project.item_ids, self.item_fle, "own items stay own")
