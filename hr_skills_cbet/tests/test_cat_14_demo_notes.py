"""UC-CAT-10 (extended) — NOTES_DEMO markdown → one rich-text body.

AC1: everything after the H1 is stored EXCEPT the per-session log table
     ("Notes du formateur (par session)" / "Trainer's notes (per session)"),
     which belongs to training lines.
AC2: EN = source, FR = translation; no-op / draft rules as for the procedure.
AC3: the authoring preamble (competency link, "Format : TWI…" line, note to
     the trainer) is dropped: the body starts at the Identification section,
     in both languages.
"""
from odoo.tests.common import tagged

from .common import CbetCommon
from .test_cat_10_import import EVAL, FICHE

NOTES = """# Notes de démonstration formateur — Compétence exemple d'import

> Compétence : [`XIM-01`](FICHE_XIM-01.md)
> Format : **TWI Job Instruction**.

---

## Identification

| Champ | Valeur |
| --- | --- |
| **Compétence ciblée** | `XIM-01` — Compétence exemple d'import |
| **Durée totale estimée** | ~60 min |

---

## Étape 1 — Préparer (10 min)

- [ ] **Banc accessible**, en état de départ.

## Étape 2 — Présenter (20 min)

| # | Étape clé | Point clé | **Raison** |
| - | --------- | --------- | ---------- |
| 1 | Pointer l'entrée | Sans toucher | Sécurité |

## Pièges fréquents (à mentionner pendant la démo)

- Confondre les deux points de lecture.

---

## Notes du formateur (par session)

> Section libre — annoter ce qui s'est bien/mal passé.

| Date | Technicien | Notes |
| --- | --- | --- |
| YYYY-MM-DD | | |
"""

NOTES_EN = """# Trainer demonstration notes — Import example competency

## Step 1 — Prepare (10 min)

- [ ] **Bench accessible**, in its starting state.

## Common pitfalls

- Confusing the two reading points.

## Trainer's notes (per session)

| Date | Technician | Notes |
| --- | --- | --- |
| YYYY-MM-DD | | |
"""


@tagged("post_install", "-at_install")
class TestCatDemoNotes(CbetCommon):
    def _fr(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        return "fr_CA"

    def test_parse_strips_the_session_log(self):
        parsed = self.env["cbet.competency"]._parse_demo_notes_md(NOTES)
        html = parsed["html"]
        self.assertIn("<h2>Identification</h2>", html)
        self.assertIn("<h2>Étape 1 — Préparer (10 min)</h2>", html)
        self.assertIn("<strong>Raison</strong>", html)
        self.assertIn("Confondre les deux points de lecture.", html)
        self.assertNotIn("Notes du formateur (par session)", html)
        self.assertNotIn("YYYY-MM-DD", html)
        self.assertNotIn("Section libre", html)
        en = self.env["cbet.competency"]._parse_demo_notes_md(NOTES_EN)["html"]
        self.assertNotIn("Trainer's notes", en)
        self.assertNotIn("YYYY-MM-DD", en)
        self.assertIn("Confusing the two reading points.", en)

    def test_import_stores_both_languages(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"NOTES_DEMO": NOTES, "NOTES_DEMO_EN": NOTES_EN})
        self.assertTrue(comp.has_demo_notes)
        self.assertIn("Bench accessible", comp.with_context(lang="en_US").demo_notes_body)
        self.assertIn("Banc accessible", comp.with_context(lang=fr).demo_notes_body)
        self.assertNotIn("YYYY-MM-DD", comp.with_context(lang=fr).demo_notes_body)

    def test_reimport_rules(self):
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(FICHE, EVAL, docs={"NOTES_DEMO": NOTES})
        comp.with_user(self.manager).action_publish()
        again, _ = Comp._import_markdown(FICHE, EVAL, docs={"NOTES_DEMO": NOTES})
        self.assertEqual(again.state, "published")
        # a new session line in the log is not content: still a no-op
        logged = NOTES.replace("| YYYY-MM-DD | | |", "| 2026-09-30 | Tech A | RAS |")
        again, _ = Comp._import_markdown(FICHE, EVAL, docs={"NOTES_DEMO": logged})
        self.assertEqual(again.state, "published")
        changed = NOTES.replace("Confondre les deux points de lecture.",
                                "Confondre les trois points de lecture.")
        again, _ = Comp._import_markdown(FICHE, EVAL, docs={"NOTES_DEMO": changed})
        self.assertEqual(again.state, "draft")


NOTES_PREAMBLE_EN = """# Trainer demonstration notes — Import example competency

> Competency: [`XIM-01`](FICHE_XIM-01_EN.md)
> Format: **TWI Job Instruction** — Prepare / Present / Try out / Follow up.
>
> Document intended for the **trainer**. A guided walk on the bench,
> no intervention.

---

## Identification

| Field | Value |
| --- | --- |
| **Target competency** | `XIM-01` — Import example competency |

## Step 1 — Prepare (10 min)

- [ ] **Bench accessible**, in its starting state.
"""


@tagged("post_install", "-at_install")
class TestCatDemoNotesPreamble(CbetCommon):
    def test_body_starts_at_identification(self):
        Comp = self.env["cbet.competency"]
        for md, gone in ((NOTES, ("Compétence :", "Format :", "TWI")),
                         (NOTES_PREAMBLE_EN, ("Competency:", "Format:", "TWI", "intended for"))):
            html = Comp._parse_demo_notes_md(md)["html"]
            self.assertTrue(html.startswith("<h2>Identification</h2>"), html[:80])
            self.assertNotIn("FICHE_XIM-01", html)
            for text in gone:
                self.assertNotIn(text, html)
        en = Comp._parse_demo_notes_md(NOTES_PREAMBLE_EN)["html"]
        self.assertIn("Bench accessible", en)
        self.assertIn("Target competency", en)

    def test_notes_without_identification_keep_their_body(self):
        html = self.env["cbet.competency"]._parse_demo_notes_md(NOTES_EN)["html"]
        self.assertTrue(html.startswith("<h2>Step 1 — Prepare (10 min)</h2>"), html[:80])
