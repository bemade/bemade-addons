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

# The vault ships an English fiche per competency (no English evaluation grid).
FICHE_EN = """# Competency Profile — Example

## Identification

| Field | Value |
| --- | --- |
| **Code** | `XIM-01` |
| **Name** | Import example competency |
| **Domain** | Example |

## 2. Prerequisites

| Code | Prerequisite competency | Mandatory |
| ---- | ----------------------- | --------- |
| `XIM-02` | Another competency | ✅ |
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

    def test_reimport_without_changes_leaves_a_published_competency_alone(self):
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        comp.with_user(self.manager).action_publish()
        crit_ids = comp.criterion_ids.ids
        again, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        self.assertEqual(again, comp)
        self.assertEqual(again.state, "published")          # untouched
        self.assertEqual(again.version, "1.0")
        # Identical content is a genuine no-op: rows are not churned.
        self.assertEqual(again.criterion_ids.ids, crit_ids)

    def test_reimport_with_changes_drafts_a_published_competency(self):
        # AC3 — published means reviewed. Re-importing changed content must not
        # rewrite a published competency behind its version number; it goes back
        # to draft so a Manager has to re-publish (which bumps and re-snapshots).
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        comp.with_user(self.manager).action_publish()
        self.assertEqual((comp.state, comp.version), ("published", "1.0"))

        changed = EVAL.replace("Bypass confirmé", "Bypass confirmé et tracé")
        again, _ = self.env["cbet.competency"]._import_markdown(FICHE, changed)
        self.assertEqual(again, comp)
        self.assertEqual(again.state, "draft")              # needs re-publishing
        self.assertEqual(again.version, "1.0")              # not silently bumped
        self.assertIn("Bypass confirmé et tracé", again.criterion_ids.mapped("text"))
        # The frozen v1.0 snapshot still describes what 1.0 actually was.
        snapshot = again.version_ids[0].snapshot
        texts = [c["text"] for u in snapshot["units"] for c in u["criteria"]]
        self.assertIn("Bypass confirmé", texts)
        self.assertNotIn("Bypass confirmé et tracé", texts)
        # Re-publishing takes it to 1.1 with a fresh snapshot.
        again.with_user(self.manager).action_publish()
        self.assertEqual((again.state, again.version), ("published", "1.1"))
        self.assertEqual(len(again.version_ids), 2)

    def test_reimport_with_changes_leaves_a_draft_in_draft(self):
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        self.assertEqual(comp.state, "draft")
        changed = EVAL.replace("Bypass confirmé", "Bypass revu")
        again, _ = self.env["cbet.competency"]._import_markdown(FICHE, changed)
        self.assertEqual(again.state, "draft")
        self.assertIn("Bypass revu", again.criterion_ids.mapped("text"))

    # ---------------------------------------------------------------- i18n
    def _fr(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        return "fr_CA"

    def test_import_captures_both_languages(self):
        # AC4 — the vault ships an English fiche alongside the French one. The
        # English lands in the source language, the French as its translation.
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL, FICHE_EN)
        self.assertEqual(comp.with_context(lang="en_US").name,
                         "Import example competency")
        self.assertEqual(comp.with_context(lang=fr).name,
                         "Compétence exemple d'import")

    def test_untranslated_content_is_french_in_both_slots(self):
        # There are no English evaluation grids yet, so Part A/B content is
        # French in both languages rather than blank in English.
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL, FICHE_EN)
        crit = comp.criterion_ids.sorted("sequence")[1]
        self.assertEqual(crit.with_context(lang="en_US").text, "Bypass confirmé")
        self.assertEqual(crit.with_context(lang=fr).text, "Bypass confirmé")
        question = comp.question_ids.sorted("sequence")[0]
        self.assertEqual(question.with_context(lang="en_US").text, "Que dois-tu isoler ?")
        self.assertEqual(question.with_context(lang=fr).text, "Que dois-tu isoler ?")

    def test_without_an_english_fiche_the_name_is_french_in_both_slots(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        self.assertEqual(comp.with_context(lang="en_US").name,
                         "Compétence exemple d'import")
        self.assertEqual(comp.with_context(lang=fr).name,
                         "Compétence exemple d'import")

    def test_adding_a_translation_does_not_draft_a_published_competency(self):
        # The French plan is the source of record. Supplying the English fiche
        # for the first time is a translation, not a revision, so it must not
        # send a published competency back to draft.
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL)
        comp.with_user(self.manager).action_publish()
        again, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL, FICHE_EN)
        self.assertEqual(again.state, "published")            # not a revision
        self.assertEqual(again.with_context(lang="en_US").name,
                         "Import example competency")          # but applied
        self.assertEqual(again.with_context(lang=fr).name,
                         "Compétence exemple d'import")

    def test_changed_french_still_drafts_even_with_an_english_fiche(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE, EVAL, FICHE_EN)
        comp.with_user(self.manager).action_publish()
        changed = EVAL.replace("Bypass confirmé", "Bypass confirmé et tracé")
        again, _ = self.env["cbet.competency"]._import_markdown(FICHE, changed, FICHE_EN)
        self.assertEqual(again.state, "draft")

    def test_domains_are_created_bilingual(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE.replace("XIM-01", "ADO-91"), EVAL)
        self.assertEqual(comp.domain_id.with_context(lang="en_US").name, "Water softener")
        self.assertEqual(comp.domain_id.with_context(lang=fr).name, "Adoucisseur")

    def test_existing_domain_gains_its_english_name(self):
        # Domains imported before the module was bilingual carry the French in
        # the source slot; the import corrects them in passing.
        fr = self._fr()
        domain = self.env["cbet.domain"].create({"code": "ADO", "name": "Adoucisseur"})
        self.env["cbet.competency"]._import_markdown(
            FICHE.replace("XIM-01", "ADO-92"), EVAL)
        self.assertEqual(domain.with_context(lang="en_US").name, "Water softener")
        self.assertEqual(domain.with_context(lang=fr).name, "Adoucisseur")

    def test_hand_edited_domain_name_is_left_alone(self):
        fr = self._fr()
        domain = self.env["cbet.domain"].create({"code": "ADO", "name": "Softeners (site)"})
        self.env["cbet.competency"]._import_markdown(
            FICHE.replace("XIM-01", "ADO-93"), EVAL)
        self.assertEqual(domain.with_context(lang="en_US").name, "Softeners (site)")

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
