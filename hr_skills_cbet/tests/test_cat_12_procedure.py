"""UC-CAT-10 (extended) — PROCEDURE markdown → one rich-text body per language.

AC1: everything after the H1 becomes html; headings and phases are kept as
     html headings.
AC2: images the archive holds are inlined as data URIs; a missing image is
     left as-is with a warning.
AC3: English edition = source value, French = translation; re-import of the
     same text is a no-op, a changed procedure drafts a published competency.
AC4: the authoring preamble (everything between the H1 and the first ``##``
     heading — competency link, sources, see-also…) is dropped, in both
     languages; the body starts at the Objective section.
AC5: scope notes of the preamble (🎯 / 🛑 / **Portée / **Hors scope /
     **Hors portée / **Frontière de portée / **Aucune intervention, and
     **Scope / **Out of scope / **Scope boundary / **No intervention) are
     kept, as a blockquote right after the Objective section's first
     paragraph (directly under the heading when it has none).
AC6: a procedure without scope notes simply loses its preamble; one without
     a preamble is unchanged.
AC7: a scope note that shares its paragraph with other preamble lines (no
     blank ``>`` line in between) is still found and kept alone.
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


PREAMBLE_FR = """# Procédure — Exemple de portée

> **Compétence :** [`XIM-03`](FICHE_XIM-03.md) — Exemple de portée
>
> 🎯 **Portée.** Procédure **générale** pour le banc d'essai,
> applicable à la plupart des bancs.
>
> **Voir aussi** : `XIM-01` (isolation), `XIM-02` (rapport).
>
> 🛑 **Hors scope — bancs spéciaux.** Les bancs spéciaux sont
> **exclus** de la présente procédure.
>
> **Sources** : [web: https://example.invalid/manuel]
>
> ➡️ **Aucune intervention sur l'équipement.** On pointe seulement.

---

## Objectif

Remplacer la cartouche du banc sans contaminer l'eau.

Deuxième paragraphe de l'objectif.

## Étapes

1. **Ouvrir** le banc.
"""

PREAMBLE_EN = """# Procedure — Scope example

> **Competency:** [`XIM-03`](FICHE_XIM-03_EN.md) — Scope example
>
> **Out of scope — special benches.** Special benches are excluded.
>
> **See also**: `XIM-01` (isolation).
>
> **Source**: bench manual. Format: **TWI Job Instruction**.

---

## Objective

Replace the bench cartridge without contaminating the water.

## Steps

1. **Open** the bench.
"""


@tagged("post_install", "-at_install")
class TestCatProcedurePreamble(CbetCommon):
    def _html(self, md):
        return self.env["cbet.competency"]._parse_procedure_md(md)["html"]

    def test_preamble_is_dropped_body_starts_at_objective(self):
        for md, heading in ((PREAMBLE_FR, "<h2>Objectif</h2>"),
                            (PREAMBLE_EN, "<h2>Objective</h2>")):
            html = self._html(md)
            self.assertTrue(html.startswith(heading), html[:80])
            for gone in ("Compétence :", "Competency:", "FICHE_XIM-03", "Voir aussi",
                         "See also", "Sources", "Source", "example.invalid",
                         "TWI", "<hr"):
                self.assertNotIn(gone, html)

    def test_scope_notes_follow_the_objective_paragraph(self):
        html = self._html(PREAMBLE_FR)
        objective = html.index("Remplacer la cartouche")
        second = html.index("Deuxième paragraphe")
        for note in ("🎯 <strong>Portée.</strong>", "🛑 <strong>Hors scope — bancs spéciaux.</strong>",
                     "➡️ <strong>Aucune intervention sur l'équipement.</strong>"):
            self.assertIn(note, html)
            self.assertTrue(objective < html.index(note) < second, note)
        # multi-line paragraphs are kept whole, in a blockquote
        self.assertIn("applicable à la plupart des bancs.", html)
        self.assertIn("<strong>exclus</strong> de la présente procédure.", html)
        quote = html[html.index("<blockquote"):html.index("</blockquote>")]
        self.assertIn("Portée", quote)
        self.assertIn("Aucune intervention", quote)
        self.assertNotIn("Deuxième paragraphe", quote)

    def test_english_scope_note_without_emoji_is_kept(self):
        html = self._html(PREAMBLE_EN)
        note = html.index("<strong>Out of scope — special benches.</strong>")
        self.assertTrue(html.index("Replace the bench cartridge") < note < html.index("<h2>Steps</h2>"))
        self.assertIn("<blockquote", html)

    def test_scope_note_goes_under_the_heading_when_there_is_no_paragraph(self):
        md = ("# Procédure — X\n\n> **Portée** : étapes après extraction.\n\n---\n\n"
              "## Objectif\n\n## Étapes\n\n1. Ouvrir.\n")
        html = self._html(md)
        self.assertTrue(html.startswith("<h2>Objectif</h2>"), html[:80])
        self.assertTrue(html.index("<strong>Portée</strong>") < html.index("<h2>Étapes</h2>"))
        self.assertIn("<blockquote", html)

    def test_preamble_without_scope_note_is_just_dropped(self):
        md = ("# Procédure — X\n\n> Compétence associée : [`XIM-04`](FICHE_XIM-04.md)\n"
              "> **Standards de référence :**\n> - Norme exemple\n\n---\n\n"
              "## Objectif\n\nIsoler le banc.\n")
        html = self._html(md)
        self.assertTrue(html.startswith("<h2>Objectif</h2>"), html[:80])
        self.assertNotIn("<blockquote", html)
        self.assertNotIn("Norme exemple", html)
        self.assertIn("Isoler le banc.", html)

    def test_procedure_without_preamble_is_unchanged(self):
        md = "# Procédure — X\n\n## Objectif\n\nIsoler le banc.\n\n> ℹ️ Note interne.\n"
        self.assertEqual(self._html(md), self.env["cbet.competency"]._parse_procedure_md(
            md.replace("# Procédure — X\n\n", ""))["html"])
        self.assertIn("ℹ️ Note interne.", self._html(md))

    def test_scope_note_inside_a_preamble_paragraph_is_kept_alone(self):
        md = ("# Procédure — X\n\n> Compétence : [`XIM-05`](FICHE_XIM-05.md)\n"
              "> **Sources** : composition des compétences existantes.\n"
              "> ⚠️ **Frontière de portée** : la **réalisation** des tests est\n"
              "> **Classe I** ; l'interprétation relève de la Classe II.\n"
              "> **Voir aussi** : `XIM-01`.\n\n---\n\n"
              "## Objectif\n\nDocumenter les tests.\n\n## Étapes\n\n1. Mesurer.\n")
        html = self._html(md)
        self.assertTrue(html.startswith("<h2>Objectif</h2>"), html[:80])
        quote = html[html.index("<blockquote"):html.index("</blockquote>")]
        self.assertIn("<strong>Frontière de portée</strong>", quote)
        self.assertIn("<strong>Classe I</strong> ; l'interprétation relève de la Classe II.", quote)
        for gone in ("Sources", "composition", "Compétence :", "Voir aussi"):
            self.assertNotIn(gone, html)
        self.assertTrue(html.index("Documenter les tests.") < html.index("<blockquote")
                        < html.index("<h2>Étapes</h2>"))
        en = self._html(md.replace("⚠️ **Frontière de portée** :", "⚠️ **Scope boundary**:"))
        self.assertIn("<strong>Scope boundary</strong>", en)
        self.assertNotIn("Sources", en)

    def test_import_cleans_both_languages(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        comp, _ = self.env["cbet.competency"]._import_markdown(
            FICHE, EVAL, docs={"PROCEDURE": PREAMBLE_FR, "PROCEDURE_EN": PREAMBLE_EN})
        en = comp.with_context(lang="en_US").procedure_body
        fr = comp.with_context(lang="fr_CA").procedure_body
        self.assertNotIn("See also", en)
        self.assertIn("Out of scope", en)
        self.assertNotIn("Voir aussi", fr)
        self.assertIn("Hors scope", fr)
