# -*- coding: utf-8 -*-
"""UC-01 — Import the curriculum from the family repository, ids preserved.

Acceptance criteria
-------------------
1. ``plan/curriculum/pda-items.csv`` (1 780 rows) imports into ``homeschool.item`` with
   ``code`` = ``pda_id`` and an **external id** ``homeschool.item_<pda_id>`` so a second
   import updates in place (idempotent: same row count, no duplicates).
2. Columns map: matiere → subject, cycle/annee, competence, section, libelle → name,
   m1..m6 (per-year markers), statut_3e, noyau, parent_id → parent, source_ref + page,
   annee_cible, priorite (core | reinvest | enrichissement | differable | ''), notes,
   projets (→ project codes, linked when the project exists).
3. ``items-internes.csv`` imports the same way with ``kind = internal`` (domaine,
   exposition, projection, section, source_ref…); ``covers.csv`` links an internal item
   to the PDA items it evidences (m2m ``covers_ids`` with basis tag).
4. ``deps-requires.csv`` creates prerequisite edges (from → to, basis, mode, note);
   endpoints may be section nodes and then apply to all descendants.
5. An unknown parent or a dangling dependency is reported (import log), never silently
   dropped; the import is transactional per file.
6. Every imported item keeps its ``source_ref`` verbatim (``PDA-US-2009 p.8-9``).
"""
from .common import HomeschoolCase


class TestCurriculumImport(HomeschoolCase):
    def test_pda_items_import_idempotent(self):
        self.skipTest("pending — TDD")

    def test_columns_mapped(self):
        self.skipTest("pending — TDD")

    def test_internal_items_and_covers(self):
        self.skipTest("pending — TDD")

    def test_dependencies(self):
        self.skipTest("pending — TDD")

    def test_dangling_references_reported(self):
        self.skipTest("pending — TDD")
