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
   imported from ``plan/curriculum/projets.csv`` and ``plan/operationnel/24`` §D.
4. A project's ``item_ids`` are the union of its own items and the items of its
   blocks and traces (computed, for the coverage view).
"""
from .common import HomeschoolCase


class TestMaterialProjects(HomeschoolCase):
    def test_material_with_attachment(self):
        self.skipTest("pending — TDD")

    def test_material_inventory_import(self):
        self.skipTest("pending — TDD")

    def test_project_states_and_vote(self):
        self.skipTest("pending — TDD")

    def test_project_items_union(self):
        self.skipTest("pending — TDD")
