# -*- coding: utf-8 -*-
"""UC-01 — Import the curriculum from the family repository, ids preserved.

Acceptance criteria
-------------------
1. ``plan/curriculum/pda-items.csv`` imports into ``homeschool.item`` with
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
    def _import(self):
        self.env["homeschool.importer"].import_projects(self.repo)
        return self.env["homeschool.importer"].import_curriculum(self.repo)

    def test_pda_items_import_idempotent(self):
        self._import()
        pda = self.Item.search([("kind", "=", "pda")]).filtered(lambda i: not i.code.startswith("T-"))
        self.assertEqual(len(pda), 5)
        self.assertTrue(self.env.ref("homeschool.item_FLE_E_SYN_C_E_2_a_i"))
        before = self.Item.search_count([])
        self._import()
        self.assertEqual(self.Item.search_count([]), before, "second import must update in place")
        self.assertEqual(self.env.ref("homeschool.item_FLE_E_SYN_C_E_2_a_i").code, "FLE-E-SYN-C-E.2.a.i")

    def test_columns_mapped(self):
        self._import()
        item = self.Item._by_code("FLE-E-SYN-C-E.2.a.i")
        self.assertEqual(item.subject_id, self.fle)
        self.assertEqual(item.name, "Encadrement du sujet par C'est… qui")
        self.assertEqual(item.competence, "Écrire")
        self.assertEqual(item.section, "Syntaxe")
        self.assertEqual(item.year_level, "5e-6e")
        self.assertTrue(item.noyau)
        self.assertEqual(item.parent_id.code, "FLE-E-SYN-C-E")
        self.assertEqual(item.source_ref, "PDA-FLE-2011 p.41")
        self.assertEqual(item.page, "41")
        self.assertEqual(item.annee_cible, "5e")
        self.assertEqual(item.priorite, "core")
        us = self.Item._by_code("US-C1-1820")
        self.assertEqual(us.source_ref, "PDA-US-2009 p.8-9")
        self.assertEqual(us.note, "Kingston")
        self.assertFalse(us.priorite)
        math = self.Item._by_code("MATH-MES-G.1")
        self.assertEqual(math.project_ids.mapped("code"), ["P-TEST"])

    def test_internal_items_and_covers(self):
        self._import()
        k1 = self.Item._by_code("K1-ENGAGE")
        self.assertEqual(k1.kind, "internal")
        self.assertEqual(k1.exposition, "internal")
        self.assertEqual(k1.source_ref, "inventaire v1")
        ela = self.Item._by_code("ELA-CONV-A")
        self.assertEqual(ela.subject_id.code, "ANG")
        covered = self.Item._by_code("FLE-E-SYN-C-E")._descendants()
        self.assertEqual(ela.covers_ids, covered, "a section covers all its descendants")
        self.assertEqual(ela.covers_basis, "[C]")
        self.assertIn(ela, self.Item._by_code("FLE-E-SYN-C-E.2.a.i").covered_by_ids)

    def test_dependencies(self):
        self._import()
        child = self.Item._by_code("FLE-E-SYN-C-E.2.a.i")
        edge = child.requires_ids
        self.assertEqual(len(edge), 1)
        self.assertEqual(edge.from_item_id.code, "FLE-E-SYN-C-E")
        self.assertEqual(edge.basis, "[P]")
        self.assertEqual(edge.mode, "hard")
        self.assertEqual(edge.note, "section first")
        # comment lines are ignored, and re-import does not duplicate edges
        self._import()
        self.assertEqual(len(child.requires_ids), 1)

    def test_dangling_references_reported(self):
        log = self._import()
        self.assertTrue(any("NOPE-1" in line for line in log), log)
        self.assertFalse(self.Item._by_code("NOPE-1"))
