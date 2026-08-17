"""UC-CAT-10 — Markdown import.

AC1: parser maps §-structured FICHE/EVALUATION into competency, criteria
     (with 🔒/⚠️/▫️ typing), Part B questions, prerequisites.
AC2: import is idempotent by competency code (re-import updates, no duplicates).
"""
import base64
import io
import zipfile

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import CbetCommon

FICHE = """# Fiche — Exemple

## Identification

| Champ | Valeur |
| --- | --- |
| **Code** | `XIM-01` |
| **Nom** | Compétence exemple d'import |
| **Domaine** | Exemple |

## 2. Prérequis

| Code | Compétence prérequise | Obligatoire |
| ---- | --------------------- | ----------- |
| `XIM-02` | Autre compétence | ✅ |
| `XIM-03` / `XIM-04` | Deux prérequis dans une cellule | Recommandé |
"""

EVAL = """# Grille — Exemple

## Partie A — Démonstration (critères de performance, fiche §8)

| # | Type | Critère (fiche §8) | Méthode / tolérance | Réussi | Échec | S.O. |
| - | ---- | ------------------ | ------------------- | :----: | :---: | :--: |
| 1 | 🔒 | **Source d'énergie** isolée | Observation · aucune | ☐ | ☐ | ☐ |
| 2 | ⚠️ | Bypass confirmé | Débit aval · confirmé | ☐ | ☐ | ☐ |
| 3 | ▫️ | Consignation au bon de travail | Vérification · complète | ☐ | ☐ | ☐ |

## Partie B — Connaissances

| # | Question (posée au candidat) | Réponse attendue (points essentiels) | Renvoi | Acquis | À revoir |
| - | ---------------------------- | ------------------------------------ | ------ | :----: | :------: |
| 1 | Que dois-tu isoler ? | Toutes les sources | §3 | ☐ | ☐ |
| 2 | Pourquoi le bypass ? | Maintenir le service | §3 | ☐ | ☐ |

> **Items essentiels (🔒/⚠️) :** questions **1 à 1** (sécurité).
"""


@tagged("post_install", "-at_install")
class TestCatImport(CbetCommon):
    def test_parse_and_import(self):
        comp, prereqs = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        self.assertEqual(comp.code, "XIM-01")
        self.assertEqual(comp.name, "Compétence exemple d'import")
        self.assertEqual(comp.domain_id.code, "XIM")
        self.assertEqual(comp.kind, "procedural")           # has Part A criteria
        # 3 criteria, typed from emoji
        types = comp.criterion_ids.sorted("sequence").mapped("criterion_type")
        self.assertEqual(types, ["security", "critical", "standard"])
        self.assertEqual(comp.criterion_ids[0].verification_method, "Observation")
        self.assertEqual(comp.criterion_ids[0].tolerance, "aucune")
        # 2 questions, Q1 essential (range "1 à 1")
        qs = comp.question_ids.sorted("sequence")
        self.assertEqual(len(qs), 2)
        self.assertTrue(qs[0].essential)
        self.assertFalse(qs[1].essential)
        # prerequisite specs parsed — incl. a multi-code cell split into two edges
        self.assertEqual(prereqs, [
            {"code": "XIM-02", "type": "obligatoire"},
            {"code": "XIM-03", "type": "recommande"},
            {"code": "XIM-04", "type": "recommande"},
        ])

    def test_import_is_idempotent(self):
        c1, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        c2, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        self.assertEqual(c1, c2)                              # same record, updated
        self.assertEqual(len(c2.criterion_ids), 3)            # not duplicated
        self.assertEqual(len(c2.question_ids), 2)

    def test_theoretical_when_no_part_a(self):
        eval_no_a = "## Partie B\n\n| # | Question | Réponse attendue | Renvoi |\n| - | - | - | - |\n| 1 | Q ? | A. | §1 |\n"
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, eval_no_a)
        self.assertEqual(comp.kind, "theoretical")
        self.assertEqual(len(comp.criterion_ids), 0)

    def test_essential_question_note_formats(self):
        Comp = self.env["cbet.competency"]
        base = ("## Partie B\n| # | Question | Réponse | Renvoi |\n| - | - | - | - |\n"
                "| 1 | Q1 | A | §1 |\n| 2 | Q2 | A | §1 |\n| 3 | Q3 | A | §1 |\n")
        # comma list "1, 3"
        r = Comp._parse_evaluation_md(
            base + "> **Items essentiels (🔒/⚠️) :** questions **1, 3** (décisions).\n")
        self.assertEqual([q["essential"] for q in r["questions"]], [True, False, True])
        # range not starting at 1 ("2 à 3")
        r2 = Comp._parse_evaluation_md(
            base + "> **Items essentiels :** questions **2 à 3** (x).\n")
        self.assertEqual([q["essential"] for q in r2["questions"]], [False, True, True])
        # mixed "1, 3 à 3" — union
        r3 = Comp._parse_evaluation_md(
            base + "> **Items essentiels :** questions **1, 3 à 3** (x).\n")
        self.assertEqual([q["essential"] for q in r3["questions"]], [True, False, True])


@tagged("post_install", "-at_install")
class TestCatImportWizard(CbetCommon):
    def test_wizard_single(self):
        wiz = self.env["cbet.import.wizard"].create({
            "import_mode": "single", "fiche_text": FICHE, "evaluation_text": EVAL})
        wiz.action_import()
        self.assertEqual(wiz.state, "done")
        self.assertEqual(wiz.imported_count, 1)
        comp = self.env["cbet.competency"].search([("code", "=", "XIM-01")])
        self.assertTrue(comp)
        self.assertEqual(len(comp.criterion_ids), 3)
        self.assertIn("XIM-01", wiz.result_log)

    def test_wizard_archive(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("vault/a/FICHE_XIM-01.md", FICHE)
            z.writestr("vault/a/EVALUATION_XIM-01.md", EVAL)
            z.writestr("vault/b/FICHE_XIT-01.md", FICHE.replace("XIM", "XIT"))
            z.writestr("vault/b/EVALUATION_XIT-01.md", EVAL)
            z.writestr("vault/a/FICHE_XIM-01_EN.md", "# english variant — ignored")
        wiz = self.env["cbet.import.wizard"].create({
            "import_mode": "archive",
            "archive_file": base64.b64encode(buf.getvalue()),
            "archive_filename": "vault.zip"})
        wiz.action_import()
        self.assertEqual(wiz.imported_count, 2)          # _EN variant ignored
        self.assertTrue(self.env["cbet.competency"].search([("code", "=", "XIT-01")]))
        self.assertTrue(self.env["cbet.competency"].search([("code", "=", "XIM-01")]))

    def test_wizard_single_bad_paste_raises(self):
        # A single paste with no parseable code surfaces a clear error (popup),
        # rather than silently reporting "0 imported".
        wiz = self.env["cbet.import.wizard"].create({
            "import_mode": "single",
            "fiche_text": "# titre sans table d'identification",
            "evaluation_text": "## Partie B\n| # | Q | A |\n| - | - | - |\n| 1 | q | a |\n"})
        with self.assertRaises(UserError):
            wiz.action_import()

    def test_wizard_archive_resilient_to_bad_pair(self):
        # One broken pair (no code in the FICHE body) is reported but does not
        # stop the valid ones from importing.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a/FICHE_XIM-01.md", FICHE)
            z.writestr("a/EVALUATION_XIM-01.md", EVAL)
            z.writestr("b/FICHE_BAD-01.md", "# no code in body")
            z.writestr("b/EVALUATION_BAD-01.md", EVAL)
        wiz = self.env["cbet.import.wizard"].create({
            "import_mode": "archive",
            "archive_file": base64.b64encode(buf.getvalue()),
            "archive_filename": "mixed.zip"})
        wiz.action_import()
        self.assertEqual(wiz.imported_count, 1)               # XIM-01 loaded
        self.assertIn("ERRORS", wiz.result_log)
        self.assertIn("BAD-01", wiz.result_log)
        self.assertTrue(self.env["cbet.competency"].search([("code", "=", "XIM-01")]))

    def test_wizard_dry_run_changes_nothing(self):
        n_comp = self.env["cbet.competency"].search_count([])
        n_crit = self.env["cbet.criterion"].search_count([])
        wiz = self.env["cbet.import.wizard"].create({
            "import_mode": "single", "fiche_text": FICHE, "evaluation_text": EVAL})
        wiz.action_dry_run()
        self.assertTrue(wiz.was_dry_run)
        self.assertEqual(wiz.imported_count, 1)               # would import 1
        self.assertIn("DRY RUN", wiz.result_log)
        self.assertIn("XIM-01", wiz.result_log)
        # unresolved prereqs (XIM-02/03/04 don't exist) are reported
        self.assertIn("UNRESOLVED", wiz.result_log)
        self.assertIn("XIM-02", wiz.result_log)
        # nothing was created
        self.assertEqual(self.env["cbet.competency"].search_count([]), n_comp)
        self.assertEqual(self.env["cbet.criterion"].search_count([]), n_crit)
        self.assertFalse(self.env["cbet.competency"].search([("code", "=", "XIM-01")]))
