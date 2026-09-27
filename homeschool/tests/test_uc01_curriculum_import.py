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
7. Subject lookup (``homeschool.subject._by_csv_key``): the exact ``code`` wins, then the
   ``csv_keys`` in subject id order (the seeded subjects win over later ones); a subject
   whose ``csv_keys`` happens to contain another subject's code never shadows it; a key
   holding a separator (``,`` / ``;``) is never one subject. The curriculum import keeps
   creating a placeholder subject for a new separator-free ``matiere`` / ``domaine``
   (``create=True``); ``create=False`` returns an empty recordset and creates nothing.
"""
import os
import shutil
import tempfile

from .common import HomeschoolCase, ITEMS_INTERNES_CSV, make_repo


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


class TestSubjectLookup(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.Subject = self.env["homeschool.subject"]
        self.ang = self.env.ref("homeschool.subject_ang")

    def _count(self):
        return self.Subject.with_context(active_test=False).search_count([])

    def test_seeded_keys_resolve(self):
        by = self.Subject._by_csv_key
        self.assertEqual(by("francais"), self.fle)
        self.assertEqual(by("FLE"), self.fle)
        self.assertEqual(by("fle"), self.fle)
        self.assertEqual(by("mathematique"), self.math)
        self.assertEqual(by("anglais_ela"), self.ang)
        self.assertEqual(by("univers_social"), self.us)
        self.assertEqual(by(" st "), self.st)
        self.assertFalse(by(""))
        self.assertFalse(by(None))

    def test_csv_keys_never_shadow_a_code(self):
        # a later subject whose keys list the codes of two real ones (the shape of the bogus
        # subject a comma-separated matieres once created)
        combo = self.Subject.create({"code": "COMBO", "name": "Combo", "csv_keys": "FLE,MATH,mathematique"})
        self.assertEqual(self.Subject._by_csv_key("FLE"), self.fle)
        self.assertEqual(self.Subject._by_csv_key("MATH"), self.math)
        self.assertEqual(self.Subject._by_csv_key("mathematique"), self.math, "seeded keys win by id order")
        self.assertEqual(self.Subject._by_csv_key("COMBO"), combo)
        # an EARLIER subject whose keys list a later subject's code: the exact code still wins
        newer = self.Subject.create({"code": "DRAMA", "name": "Drama", "csv_keys": "art_dramatique"})
        self.fle.csv_keys = "francais,FLE,fle,DRAMA"
        self.assertEqual(self.Subject._by_csv_key("DRAMA"), newer)
        self.assertEqual(self.Subject._by_csv_key("art_dramatique"), newer)

    def test_separator_key_is_never_one_subject(self):
        n = self._count()
        for key in ("FLE,MATH", "FLE;MATH", "francais, mathematique", ";"):
            self.assertFalse(self.Subject._by_csv_key(key), key)
            self.assertFalse(self.Subject._by_csv_key(key, create=True), key)
            self.assertFalse(self.Subject._by_csv_key(key, create=False), key)
        self.assertEqual(self._count(), n, "no placeholder for a separator key")

    def test_create_flag(self):
        n = self._count()
        self.assertFalse(self.Subject._by_csv_key("arts_plastiques", create=False))
        self.assertEqual(self._count(), n)
        created = self.Subject._by_csv_key("arts_plastiques")
        self.assertTrue(created, "curriculum imports keep the placeholder behaviour")
        self.assertEqual((created.code, created.csv_keys), ("ARTS_PLASTIQUES", "arts_plastiques"))
        self.assertEqual(self._count(), n + 1)
        self.assertEqual(self.Subject._by_csv_key("arts_plastiques", create=False), created, "…and it resolves afterwards")
        self.assertEqual(self._count(), n + 1)

    def test_curriculum_import_placeholder_for_new_domaine(self):
        root = make_repo(tempfile.mkdtemp(prefix="homeschool-curriculum-"))
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        with open(os.path.join(root, "plan", "curriculum", "items-internes.csv"), "w", encoding="utf-8") as fh:
            fh.write(ITEMS_INTERNES_CSV + "ART-1,arts_plastiques,internal,,Collage,A,,,,,,,,inventaire v1,,\n")
        n = self._count()
        self.env["homeschool.importer"].import_curriculum(root)
        self.assertEqual(self.Item._by_code("FLE-E-SYN-C-E.2.a.i").subject_id, self.fle)
        self.assertEqual(self.Item._by_code("MATH-MES-G.1").subject_id, self.math)
        self.assertEqual(self.Item._by_code("US-C1-1820").subject_id, self.us)
        self.assertEqual(self.Item._by_code("ST-MAT-D.4.a").subject_id, self.st)
        self.assertEqual(self.Item._by_code("ELA-CONV-A").subject_id, self.ang)
        art = self.Item._by_code("ART-1")
        self.assertEqual(art.subject_id.code, "ARTS_PLASTIQUES", "a new separator-free domaine still gets a placeholder")
        self.assertEqual(self._count(), n + 1)
