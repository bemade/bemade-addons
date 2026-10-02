"""UC-CAT-10 (extended) — the full FICHE lands in the competency.

AC1: every numbered section is stored in its field; the structured sections
     (§9 protocol, §10 evaluator, §12 validity, §13 meta) are parsed into the
     existing/typed fields rather than kept as prose.
AC2: a section reading "Sans objet" leaves its field empty.
AC3: duration / validity / difficulty are mapped to numbers and selections.
AC4: English editions become the source value, French the translation, for
     every new field; identical markdown re-imports as a true no-op.
"""
from odoo.tests.common import tagged

from .common import CbetCommon

FICHE_FULL = """# Fiche de compétence — Compétence exemple complète

> Compétence de **reconnaissance (niveau 1)** — démontrée **sur banc d'essai**.

---

## Identification

| Champ | Valeur |
| --- | --- |
| **Code** | `XIM-01` |
| **Nom** | Compétence exemple complète |
| **Domaine** | Exemple |

---

## 1. Contexte d'exécution

| Élément | Détail |
| --- | --- |
| Types d'équipement couverts | Bancs d'essai de démonstration. |
| Types **exclus** | Bancs hors portée. |
| Environnement | Atelier. |

---

## 2. Prérequis

| Code | Compétence prérequise | Obligatoire |
| ---- | --------------------- | ----------- |
| `XIM-02` | Autre compétence | ✅ |
| `XIM-03` | Encore une autre | Recommandé |

---

## 3. Connaissances sous-jacentes (théorie minimale requise)

### Glossaire / terminologie

- **Banc d'essai** — montage d'atelier reproduisant le circuit.
- **Point de lecture** — endroit où une valeur est relevée.

### 3.1 Principe

- Le banc permet de nommer les composantes sans intervenir.

---

## 4. Sécurité

### 4.1 Exigences générales

- [x] **Zone de travail** dégagée.
- [ ] Cadenassage — *non requis*.

### 4.2 Risques typiques

- [x] Projections (liquide sous pression)

---

## 5. Outils et matériel requis

- Support de formation : **coupe de démonstration** d'un banc.
- **Schéma annoté** du circuit.

---

## 6. Documents requis sur place

- [ ] Schéma annoté du circuit
- [ ] Références : voir **§14 Références**

---

## 7. Procédure / aide-mémoire

- **Procédure complète** : [`PROCEDURE_XIM-01.md`](PROCEDURE_XIM-01.md).

---

## 8. Critères de performance mesurables

| # | Type | Critère | Méthode de vérification | Tolérance |
| - | ---- | ------- | ----------------------- | --------- |
| 1 | 🔒 | Accès sécuritaire assuré | Observation | Aucune |

---

## 9. Protocole d'évaluation

| Élément | Détail |
| --- | --- |
| **Méthode** | **Démonstration sur banc** — le candidat **pointe et explique**. |
| **Lieu** | Atelier de formation. |
| **Durée prévue** | ~45 min (briefing + exécution + débriefing). |
| **Conditions de départ** | Banc accessible ; aucune intervention. |
| **Accompagnement permis pendant l'éval** | Aucun (évaluation de connaissance). |
| **Verbalisation requise** | Le candidat **nomme les composantes** à voix haute. |

> 🗓️ Cette compétence peut être évaluée dans une même session avec d'autres.

---

## 10. Évaluateur qualifié

| Critère | Exigence |
| --- | --- |
| Niveau minimum | **Formateur désigné.** |
| Indépendance | De préférence pas le formateur direct du candidat. |

---

## 11. Évidences à conserver

- [ ] **Grille d'évaluation signée** (évaluateur + technicien)
- [ ] Date, lieu

**Conservation :** dossier employé, 7 ans.

---

## 12. Validité et recyclage

| Élément | Valeur |
| --- | --- |
| **Durée de validité** | **18 mois** |
| **Conditions de maintien** | **≥ 2 interventions** dans les 18 mois ; à défaut, **recertification**. |
| **Modalité de recertification** | Démonstration de reconnaissance sur banc. |
| **Déclencheur de recertification anticipée** | Changement majeur de banc / doute sur la maîtrise. |

---

## 13. Méta — pour le formateur

| Élément | Valeur |
| --- | --- |
| Fréquence terrain (data 2024+) | **Prérequis fondamental** du domaine Exemple. |
| Difficulté perçue | Faible à moyenne (volume de vocabulaire). |
| Temps estimé d'apprentissage | ~1 h démo + pratique supervisée. |
| Pièges fréquents | Confondre les deux points de lecture ; oublier la zone dégagée. |
| Lien vers analyse terrain | `_archives/ANALYSE.md` |

---

## 14. Références

| # | Référence |
| --- | --- |
| [1] | Fabricant Exemple — *Manuel du banc d'essai* (doc 0001) |
"""

FICHE_FULL_EN = """# Competency profile — Full example competency

> **Recognition (level 1)** competency — demonstrated **on a test bench**.

---

## Identification

| Field | Value |
| --- | --- |
| **Code** | `XIM-01` |
| **Name** | Full example competency |
| **Domain** | Example |

---

## 1. Execution context

| Element | Detail |
| --- | --- |
| Types of equipment covered | Demonstration test benches. |
| **Excluded** types | Benches out of scope. |
| Environment | Workshop. |

---

## 2. Prerequisites

| Code | Prerequisite competency | Mandatory |
| ---- | ----------------------- | --------- |
| `XIM-02` | Another competency | ✅ |
| `XIM-03` | Yet another one | Recommended |

---

## 3. Underlying knowledge (minimum theory required)

### Glossary / terminology

- **Test bench** — workshop rig reproducing the circuit.
- **Reading point** — where a value is read.

### 3.1 Principle

- The bench lets you name the components without intervening.

---

## 4. Safety

### 4.1 General requirements

- [x] **Work area** cleared.
- [ ] Lockout — *not required*.

---

## 5. Required tools and materials

- Training support: **demonstration cutaway** of a bench.

---

## 6. Documents required on site

- [ ] Annotated circuit diagram

---

## 7. Procedure / quick reference

- **Full procedure**: [`PROCEDURE_XIM-01_EN.md`](PROCEDURE_XIM-01_EN.md).

---

## 8. Measurable performance criteria

| # | Type | Criterion | Verification method | Tolerance |
| - | ---- | --------- | ------------------- | --------- |
| 1 | 🔒 | Safe access ensured | Observation | None |

---

## 9. Assessment protocol

| Element | Detail |
| --- | --- |
| **Method** | **Demonstration on a bench** — the candidate **points out and explains**. |
| **Location** | Training workshop. |
| **Expected duration** | ~45 min (briefing + execution + debriefing). |
| **Starting conditions** | Bench accessible; no intervention. |
| **Support allowed during assessment** | None (knowledge assessment). |
| **Verbalization required** | The candidate **names the components** out loud. |

---

## 10. Qualified evaluator

| Criterion | Requirement |
| --- | --- |
| Minimum level | **Designated trainer.** |
| Independence | Preferably not the candidate's direct trainer. |

---

## 11. Records to retain

- [ ] **Signed evaluation grid** (evaluator + technician)
- [ ] Date, place

---

## 12. Validity and recertification

| Element | Value |
| --- | --- |
| **Validity period** | **18 months** |
| **Maintenance conditions** | **≥ 2 interventions** within 18 months; otherwise **recertification**. |
| **Recertification method** | Recognition demonstration on a bench. |
| **Early-recertification trigger** | Major bench change / doubt about mastery. |

---

## 13. Meta — for the trainer

| Element | Value |
| --- | --- |
| Field frequency (2024+ data) | **Fundamental prerequisite** of the Example domain. |
| Perceived difficulty | Low to medium (volume of vocabulary). |
| Estimated learning time | ~1 h demo + supervised practice. |
| Common pitfalls | Confusing the two reading points; forgetting the cleared area. |

---

## 14. References

| # | Reference |
| --- | --- |
| [1] | Example Manufacturer — *Test bench manual* (doc 0001) |
"""

EVAL = """# Grille — Exemple

## Partie A — Démonstration

| # | Type | Critère | Méthode / tolérance | Réussi | Échec | S.O. |
| - | ---- | ------- | ------------------- | :----: | :---: | :--: |
| 1 | 🔒 | Accès sécuritaire assuré | Observation · aucune | ☐ | ☐ | ☐ |

## Partie B — Connaissances

| # | Question | Réponse attendue | Renvoi | Acquis | À revoir |
| - | -------- | ---------------- | ------ | :----: | :------: |
| 1 | Nomme les deux points de lecture. | Entrée, sortie | §3 | ☐ | ☐ |

> **Items essentiels (🔒/⚠️) :** questions **1 à 1**.
"""


@tagged("post_install", "-at_install")
class TestCatFicheFull(CbetCommon):
    def _fr(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        return "fr_CA"

    def test_parse_fiche_sections(self):
        parsed = self.env["cbet.competency"]._parse_fiche_md(FICHE_FULL)
        self.assertEqual(parsed["code"], "XIM-01")
        self.assertEqual(parsed["subtitle"],
                         "Compétence de reconnaissance (niveau 1) — démontrée sur banc d'essai.")
        # prose sections are html
        self.assertIn("<table>", parsed["execution_context"])
        self.assertIn("Bancs d'essai de démonstration.", parsed["execution_context"])
        self.assertIn("<h3>Glossaire / terminologie</h3>", parsed["knowledge_body"])
        self.assertIn("<strong>Banc d'essai</strong>", parsed["knowledge_body"])
        # checklists survive as text boxes, not stripped <input> elements
        self.assertIn("☑ <strong>Zone de travail</strong>", parsed["safety_block"])
        self.assertIn("☐ Cadenassage", parsed["safety_block"])
        self.assertNotIn("<input", parsed["safety_block"])
        self.assertIn("coupe de démonstration", parsed["tools_materials"])
        self.assertIn("Schéma annoté du circuit", parsed["documents_required"])
        self.assertIn("Grille d'évaluation signée", parsed["evidence_required"])
        self.assertIn("Manuel du banc d'essai", parsed["references_body"])
        self.assertIn("<table>", parsed["references_body"])
        # §9 protocol
        p = parsed["protocol"]
        self.assertEqual(p["method"], "Démonstration sur banc — le candidat pointe et explique.")
        self.assertEqual(p["place"], "Atelier de formation.")
        self.assertAlmostEqual(p["duration"], 0.75)
        self.assertEqual(p["start_conditions"], "Banc accessible ; aucune intervention.")
        self.assertEqual(p["support"], "Aucun (évaluation de connaissance).")
        self.assertEqual(p["verbalization"], "Le candidat nomme les composantes à voix haute.")
        # §10
        self.assertEqual(parsed["evaluator"]["min_qualification"], "Formateur désigné.")
        self.assertEqual(parsed["evaluator"]["independence"],
                         "De préférence pas le formateur direct du candidat.")
        # §12
        v = parsed["validity"]
        self.assertEqual(v["months"], 18)
        self.assertIn("≥ 2 interventions", v["maintenance_condition"])
        self.assertEqual(v["recert_modality"], "Démonstration de reconnaissance sur banc.")
        self.assertIn("Changement majeur de banc", v["recert_early_trigger"])
        # §13
        m = parsed["meta"]
        self.assertEqual(m["field_frequency"], "Prérequis fondamental du domaine Exemple.")
        self.assertEqual(m["difficulty"], "medium")
        self.assertEqual(m["learning_time"], "~1 h démo + pratique supervisée.")
        self.assertIn("Confondre les deux points de lecture", m["common_pitfalls"])

    def test_sections_are_located_by_number_not_title(self):
        md = FICHE_FULL.replace("## 5. Outils et matériel requis", "## 5. Matériel")
        parsed = self.env["cbet.competency"]._parse_fiche_md(md)
        self.assertIn("coupe de démonstration", parsed["tools_materials"])

    def test_sans_objet_leaves_the_field_empty(self):
        md = FICHE_FULL.replace(
            "- Support de formation : **coupe de démonstration** d'un banc.\n"
            "- **Schéma annoté** du circuit.",
            "**Sans objet** — compétence de connaissance (aucune intervention terrain).")
        parsed = self.env["cbet.competency"]._parse_fiche_md(md)
        self.assertEqual(parsed["tools_materials"], "")
        comp, _ = self.env["cbet.competency"]._import_markdown(md, EVAL)
        self.assertFalse(comp.tools_materials)

    def test_value_mappings(self):
        Comp = self.env["cbet.competency"]
        self.assertAlmostEqual(Comp._parse_duration_hours("1 h 30"), 1.5)
        self.assertAlmostEqual(Comp._parse_duration_hours("~2 h démo"), 2.0)
        self.assertAlmostEqual(Comp._parse_duration_hours("90 min incluant briefing"), 1.5)
        self.assertAlmostEqual(Comp._parse_duration_hours("~20–30 min."), 20 / 60)
        self.assertEqual(Comp._parse_duration_hours("à déterminer"), 0.0)
        self.assertEqual(Comp._parse_validity_months("**12 mois**"), 12)
        self.assertEqual(Comp._parse_validity_months("24 months"), 24)
        self.assertEqual(Comp._parse_validity_months("2 ans"), 24)
        self.assertIsNone(Comp._parse_validity_months("—"))
        self.assertEqual(Comp._parse_difficulty("Élevée — geste délicat"), "high")
        self.assertEqual(Comp._parse_difficulty("High"), "high")
        self.assertEqual(Comp._parse_difficulty("Faible à moyenne"), "medium")
        self.assertEqual(Comp._parse_difficulty("Medium"), "medium")
        self.assertEqual(Comp._parse_difficulty("Faible"), "low")
        self.assertIsNone(Comp._parse_difficulty(""))

    def test_import_lands_every_section(self):
        comp, prereqs = self.env["cbet.competency"]._import_markdown(FICHE_FULL, EVAL)
        self.assertEqual(comp.subtitle,
                         "Compétence de reconnaissance (niveau 1) — démontrée sur banc d'essai.")
        self.assertIn("Bancs d'essai de démonstration.", comp.execution_context)
        self.assertIn("Glossaire", comp.knowledge_body)
        self.assertIn("☑", comp.safety_block)
        self.assertIn("coupe de démonstration", comp.tools_materials)
        self.assertIn("Schéma annoté du circuit", comp.documents_required)
        self.assertIn("Grille d'évaluation signée", comp.evidence_required)
        self.assertIn("Manuel du banc d'essai", comp.references_body)
        self.assertEqual(comp.protocol_method,
                         "Démonstration sur banc — le candidat pointe et explique.")
        self.assertEqual(comp.protocol_place, "Atelier de formation.")
        self.assertAlmostEqual(comp.protocol_duration, 0.75)
        self.assertEqual(comp.protocol_support, "Aucun (évaluation de connaissance).")
        self.assertEqual(comp.protocol_start_conditions, "Banc accessible ; aucune intervention.")
        self.assertEqual(comp.protocol_verbalization,
                         "Le candidat nomme les composantes à voix haute.")
        self.assertEqual(comp.protocol_min_evaluator_qualification, "Formateur désigné.")
        self.assertEqual(comp.evaluator_independence,
                         "De préférence pas le formateur direct du candidat.")
        # §12 — the fiche's value, not the company default (24)
        self.assertEqual(comp.validity_months, 18)
        self.assertIn("≥ 2 interventions", comp.maintenance_condition)
        self.assertEqual(comp.recert_modality, "Démonstration de reconnaissance sur banc.")
        self.assertIn("Changement majeur de banc", comp.recert_early_trigger)
        # §13
        self.assertEqual(comp.field_frequency, "Prérequis fondamental du domaine Exemple.")
        self.assertEqual(comp.difficulty, "medium")
        self.assertEqual(comp.learning_time, "~1 h démo + pratique supervisée.")
        self.assertIn("Confondre les deux points de lecture", comp.common_pitfalls)
        # §2 still feeds the prerequisite pass
        self.assertEqual([p["code"] for p in prereqs], ["XIM-02", "XIM-03"])
        self.assertFalse(comp.has_procedure)
        self.assertFalse(comp.has_job_aid)
        self.assertFalse(comp.has_demo_notes)

    def test_fiche_without_a_validity_keeps_the_default(self):
        md = FICHE_FULL.replace("| **Durée de validité** | **18 mois** |",
                                "| **Durée de validité** | — |")
        comp, _ = self.env["cbet.competency"]._import_markdown(md, EVAL)
        self.assertEqual(comp.validity_months, self.env.company.cbet_default_validity_months)

    def test_english_fiche_is_the_source_french_the_translation(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE_FULL, EVAL, FICHE_FULL_EN)
        en, fr_ = comp.with_context(lang="en_US"), comp.with_context(lang=fr)
        self.assertEqual(en.subtitle,
                         "Recognition (level 1) competency — demonstrated on a test bench.")
        self.assertEqual(fr_.subtitle,
                         "Compétence de reconnaissance (niveau 1) — démontrée sur banc d'essai.")
        self.assertIn("Demonstration test benches.", en.execution_context)
        self.assertIn("Bancs d'essai de démonstration.", fr_.execution_context)
        self.assertNotIn("Bancs d'essai", en.execution_context)
        self.assertIn("<h3>Glossary / terminology</h3>", en.knowledge_body)
        self.assertIn("<h3>Glossaire / terminologie</h3>", fr_.knowledge_body)
        self.assertIn("Signed evaluation grid", en.evidence_required)
        self.assertIn("Grille d'évaluation signée", fr_.evidence_required)
        self.assertIn("Test bench manual", en.references_body)
        self.assertIn("Manuel du banc d'essai", fr_.references_body)
        self.assertEqual(en.protocol_method,
                         "Demonstration on a bench — the candidate points out and explains.")
        self.assertEqual(fr_.protocol_method,
                         "Démonstration sur banc — le candidat pointe et explique.")
        self.assertEqual(en.protocol_min_evaluator_qualification, "Designated trainer.")
        self.assertEqual(fr_.protocol_min_evaluator_qualification, "Formateur désigné.")
        self.assertEqual(en.recert_modality, "Recognition demonstration on a bench.")
        self.assertEqual(fr_.recert_modality, "Démonstration de reconnaissance sur banc.")
        self.assertEqual(en.learning_time, "~1 h demo + supervised practice.")
        self.assertEqual(fr_.learning_time, "~1 h démo + pratique supervisée.")
        self.assertEqual(en.field_frequency, "Fundamental prerequisite of the Example domain.")
        self.assertEqual(fr_.field_frequency, "Prérequis fondamental du domaine Exemple.")
        self.assertIn("Confusing the two reading points", en.common_pitfalls)
        self.assertIn("Confondre les deux points", fr_.common_pitfalls)
        # The structured values are language-independent.
        self.assertEqual(comp.validity_months, 18)
        self.assertEqual(comp.difficulty, "medium")

    def test_import_under_a_french_user_still_puts_the_english_in_en_us(self):
        fr = self._fr()
        Comp = self.env["cbet.competency"].with_context(lang=fr)
        comp, _ = Comp._import_markdown(FICHE_FULL, EVAL, FICHE_FULL_EN)
        self.assertIn("<h3>Glossary / terminology</h3>", comp.with_context(lang="en_US").knowledge_body)
        self.assertIn("<h3>Glossaire / terminologie</h3>", comp.with_context(lang=fr).knowledge_body)
        self.assertEqual(comp.with_context(lang="en_US").protocol_min_evaluator_qualification,
                         "Designated trainer.")
        self.assertEqual(comp.with_context(lang=fr).protocol_min_evaluator_qualification,
                         "Formateur désigné.")
        # a corrected English edition, re-imported by the same French user, lands in en_US
        Comp._import_markdown(FICHE_FULL, EVAL,
                              FICHE_FULL_EN.replace("Designated trainer.", "Certified trainer."))
        self.assertEqual(comp.with_context(lang="en_US").protocol_min_evaluator_qualification,
                         "Certified trainer.")
        self.assertEqual(comp.with_context(lang=fr).protocol_min_evaluator_qualification,
                         "Formateur désigné.")

    def test_quiz_row_rides_with_the_method_and_traps_are_pitfalls(self):
        md = (
            "# Fiche de compétence — Q\n\n## Identification\n\n| Champ | Valeur |\n| --- | --- |\n"
            "| **Code** | `XIQ-01` |\n| **Nom** | Q |\n\n"
            "## 9. Protocole d'évaluation\n\n| Élément | Détail |\n| --- | --- |\n"
            "| **Méthode** | Démonstration. |\n| **Quiz de récupération** | Oral, 5 questions. |\n\n"
            "## 13. Méta — pour le formateur\n\n| Élément | Valeur |\n| --- | --- |\n"
            "| Frequent traps | Mixing up the two reading points. |\n"
        )
        fiche = self.env["cbet.competency"]._parse_fiche_md(md)
        self.assertEqual(fiche["protocol"]["method"], "Démonstration. — Quiz : Oral, 5 questions.")
        self.assertEqual(fiche["meta"]["common_pitfalls"], "Mixing up the two reading points.")

    def test_duration_takes_the_leading_figure(self):
        parse = self.env["cbet.competency"]._parse_duration_hours
        self.assertEqual(parse("~30 min (puis 8 h de pratique)"), 0.5)
        self.assertEqual(parse("1 h 30"), 1.5)
        self.assertAlmostEqual(parse("~20–30 min."), 20 / 60)   # a range reads its lower bound

    def test_empty_french_body_keeps_the_english(self):
        fr = self._fr()
        comp = self.env["cbet.competency"].create({"code": "XIE-01", "name": "E"})
        comp._write_imported_fiche({"validity": {}, "protocol": {}},
                                   {"safety_block": "<p>Gloves at all times.</p>"})
        self.assertIn("Gloves", comp.with_context(lang="en_US").safety_block)
        self.assertIn("Gloves", comp.with_context(lang=fr).safety_block)

    def test_without_english_the_french_fills_both_languages(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(FICHE_FULL, EVAL)
        self.assertIn("Glossaire", comp.with_context(lang="en_US").knowledge_body)
        self.assertIn("Glossaire", comp.with_context(lang=fr).knowledge_body)
        self.assertEqual(comp.with_context(lang="en_US").protocol_place, "Atelier de formation.")
        self.assertEqual(comp.with_context(lang=fr).protocol_place, "Atelier de formation.")

    def test_reimport_identical_fiche_is_a_no_op_on_a_published_competency(self):
        fr = self._fr()
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(FICHE_FULL, EVAL, FICHE_FULL_EN)
        comp.with_user(self.manager).action_publish()
        again, _ = Comp._import_markdown(FICHE_FULL, EVAL, FICHE_FULL_EN)
        self.assertEqual(again, comp)
        self.assertEqual(again.state, "published")
        # and the languages are still intact afterwards
        self.assertIn("Glossary", again.with_context(lang="en_US").knowledge_body)
        self.assertIn("Glossaire", again.with_context(lang=fr).knowledge_body)

    def test_changed_knowledge_drafts_a_published_competency(self):
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(FICHE_FULL, EVAL)
        comp.with_user(self.manager).action_publish()
        changed = FICHE_FULL.replace("- Le banc permet de nommer les composantes sans intervenir.",
                                     "- Le banc permet de nommer les composantes et les cycles.")
        again, _ = Comp._import_markdown(changed, EVAL)
        self.assertEqual(again.state, "draft")
        self.assertIn("et les cycles", again.knowledge_body)

    def test_late_english_fiche_lands_without_drafting(self):
        fr = self._fr()
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(FICHE_FULL, EVAL)
        comp.with_user(self.manager).action_publish()
        again, _ = Comp._import_markdown(FICHE_FULL, EVAL, FICHE_FULL_EN)
        self.assertEqual(again.state, "published")
        self.assertIn("Glossary", again.with_context(lang="en_US").knowledge_body)
        self.assertIn("Glossaire", again.with_context(lang=fr).knowledge_body)
        self.assertEqual(again.with_context(lang="en_US").protocol_place, "Training workshop.")
        self.assertEqual(again.with_context(lang=fr).protocol_place, "Atelier de formation.")

    def test_editing_one_language_keeps_the_other(self):
        # Risk noted in the plan: the bodies are whole-document per language,
        # so a later edit in one language must not blank the other.
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE_FULL, EVAL, FICHE_FULL_EN)
        comp.with_context(lang=fr).write({"knowledge_body": "<p>Nouveau texte</p>"})
        self.assertEqual(comp.with_context(lang=fr).knowledge_body, "<p>Nouveau texte</p>")
        self.assertIn("Glossary", comp.with_context(lang="en_US").knowledge_body)
