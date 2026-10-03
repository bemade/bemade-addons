"""UC-CAT-10 (extended) — PROCEDURE markdown → one rich-text body per language.

AC1: everything after the H1 becomes html; headings and phases are kept as
     html headings.
AC2: images the archive holds are inlined as data URIs; a missing image is
     left as-is with a warning.
AC3: English edition = source value, French = translation; re-import of the
     same text is a no-op, a changed procedure drafts a published competency.
"""
import base64

import re

from odoo.tests.common import tagged

from .common import CbetCommon
from .test_cat_10_import import EVAL, FICHE

PROCEDURE = """# Procédure — Compétence exemple d'import

> Compétence : [`XIM-01`](FICHE_XIM-01.md)
> ➡️ **Aucune intervention sur l'équipement.**

---

## Objectif

Reconnaître et nommer les composantes du banc.

## Conditions de départ

- [ ] `XIM-02` **acquis**.
- [ ] Accès au **banc d'essai**.

## Sécurité (points clés)
- 🥽 **Lunettes de sécurité** — toujours obligatoires.

---

## Étapes

### Phase 1 — Cadrer *(observation visuelle)*

1. **Confirmer l'accès** au banc.
2. **Annoncer la règle** : on pointe, on ne touche pas.

### Phase 2 — Expliquer

3. **Définir** le point de lecture.

![Schéma du banc](images/banc.png)

| Repère | Valeur |
| --- | --- |
| Entrée | 10 |
"""

PROCEDURE_EN = """# Procedure — Import example competency

> Competency: [`XIM-01`](FICHE_XIM-01_EN.md)

---

## Objective

Recognise and name the bench components.

## Steps

### Phase 1 — Frame *(visual observation)*

1. **Confirm access** to the bench.

![Bench diagram](images/banc.png)
"""

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")


@tagged("post_install", "-at_install")
class TestCatProcedure(CbetCommon):
    def _fr(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        return "fr_CA"

    def test_parse_procedure_body(self):
        parsed = self.env["cbet.competency"]._parse_procedure_md(PROCEDURE)
        html = parsed["html"]
        self.assertNotIn("Procédure — Compétence exemple d'import", html)   # H1 dropped
        self.assertIn("<h2>Objectif</h2>", html)
        self.assertIn("<h3>Phase 1 — Cadrer <em>(observation visuelle)</em></h3>", html)
        self.assertIn("<ol>", html)
        self.assertIn("☐ <code>XIM-02</code> <strong>acquis</strong>.", html)
        self.assertIn("<table>", html)
        self.assertNotIn("<input", html)
        # no archive → image left as-is, with a warning
        self.assertIn('src="images/banc.png"', html)
        self.assertEqual(parsed["warnings"], ["image not found in archive: images/banc.png"])

    def test_callout_inside_a_list_item_keeps_the_list_and_drops_the_marker(self):
        md = (
            "# Procédure — X\n\n## Étapes\n\n"
            "1. **Rétrolavage** : inverser le débit.\n"
            "2. **Saumurage** : injecter la saumure.\n"
            "     > ℹ️ **Unité** : lecture au salomètre.\n"
            "     > Cible 30 %.\n"
            "3. **Rinçage lent**.\n"
        )
        html = self.env["cbet.competency"]._parse_procedure_md(md)["html"]
        self.assertEqual(html.count("<li>"), 3)          # one list, three items
        self.assertNotIn("&gt;", html)
        self.assertNotIn(">", re.sub(r"<[^>]+>", "", html))   # no stray quote marker
        self.assertIn("ℹ️ <strong>Unité</strong> : lecture au salomètre.", html)
        self.assertIn("Cible 30 %.", html)
        # a top-level blockquote is still a blockquote
        top = self.env["cbet.competency"]._parse_procedure_md("# P\n\n> ➡️ Note.\n")["html"]
        self.assertIn("<blockquote", top)

    def test_callout_after_a_table_is_a_paragraph_not_a_code_block(self):
        md = (
            "# Procédure — X\n\n## Étapes\n\n"
            "16. **Ordonner** les cycles :\n\n"
            "    | # | Cycle |\n    | - | ----- |\n    | 1 | Rétrolavage |\n\n"
            "     > ℹ️ **Cible** : au moins 30 % au salomètre.\n"
            "     > Toujours préciser l'unité.\n\n"
            "17. **Clore** la visite.\n"
        )
        html = self.env["cbet.competency"]._parse_procedure_md(md)["html"]
        self.assertNotIn("<pre>", html)
        self.assertIn("ℹ️ <strong>Cible</strong> : au moins 30 % au salomètre.", html)
        self.assertIn("<table>", html)
        # a genuine code block (ASCII diagram) is left alone
        diagram = "# P\n\n## Montage\n\n    Bac --- Canne --- Aspirateur\n    |         |\n"
        self.assertIn("<pre>", self.env["cbet.competency"]._parse_procedure_md(diagram)["html"])

    def test_images_are_inlined_from_the_archive(self):
        def loader(path):
            return PNG if path == "images/banc.png" else None
        parsed = self.env["cbet.competency"]._parse_procedure_md(PROCEDURE, loader)
        self.assertIn('src="data:image/png;base64,', parsed["html"])
        self.assertIn('alt="Schéma du banc"', parsed["html"])
        self.assertNotIn("images/banc.png", parsed["html"])
        self.assertEqual(parsed["warnings"], [])

    def test_import_stores_the_body_in_both_languages(self):
        fr = self._fr()
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(
            FICHE, EVAL, docs={"PROCEDURE": PROCEDURE, "PROCEDURE_EN": PROCEDURE_EN})
        self.assertTrue(comp.has_procedure)
        self.assertIn("<h2>Objective</h2>", comp.with_context(lang="en_US").procedure_body)
        self.assertIn("<h2>Objectif</h2>", comp.with_context(lang=fr).procedure_body)
        self.assertNotIn("Objectif", comp.with_context(lang="en_US").procedure_body)

    def test_french_only_procedure_fills_both_languages(self):
        fr = self._fr()
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"PROCEDURE": PROCEDURE})
        self.assertIn("<h2>Objectif</h2>", comp.with_context(lang="en_US").procedure_body)
        self.assertIn("<h2>Objectif</h2>", comp.with_context(lang=fr).procedure_body)

    def test_reimport_same_procedure_is_a_no_op_changed_one_drafts(self):
        Comp = self.env["cbet.competency"]
        comp, _ = Comp._import_markdown(FICHE, EVAL, docs={"PROCEDURE": PROCEDURE})
        comp.with_user(self.manager).action_publish()
        again, _ = Comp._import_markdown(FICHE, EVAL, docs={"PROCEDURE": PROCEDURE})
        self.assertEqual(again.state, "published")
        changed = PROCEDURE.replace("on pointe, on ne touche pas", "on pointe seulement")
        again, _ = Comp._import_markdown(FICHE, EVAL, docs={"PROCEDURE": changed})
        self.assertEqual(again.state, "draft")
        self.assertIn("on pointe seulement", again.procedure_body)
        # the chatter explains why
        self.assertTrue(any("back to draft" in (m.body or "") for m in again.message_ids))

    def test_warnings_are_collected(self):
        warnings = []
        self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"PROCEDURE": PROCEDURE}, warnings=warnings)
        self.assertEqual(warnings, [("XIM-01", "PROCEDURE: image not found in archive: images/banc.png")])
