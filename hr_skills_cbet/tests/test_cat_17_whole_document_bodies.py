"""UC-CAT-08 guard — the document bodies are translated as WHOLE documents.

The fiche sections, the procedure, the trainer demo notes and the job-aid
reference notes are authored independently in French and in English. In Odoo
19 a *sanitized* ``Html(translate=True)`` field silently becomes term-based
(``html_translate``): writing the French then rebuilds the English from the
French structure, and vice versa — which would clobber the other language's
document. ``sanitize=False`` is what keeps one whole document per language
(the importer sanitizes everything it produces instead).

AC1: every document body field is translated whole, not term by term.
AC2: writing one language's body does not alter the other language's body.

If this test fails because ``sanitize=True`` was reintroduced on one of these
fields, do NOT relax the test: restore ``sanitize=False`` and keep the
sanitizing where the html is produced.
"""
from odoo.tests.common import tagged

from .common import CbetCommon

COMPETENCY_BODIES = (
    "execution_context",
    "knowledge_body",
    "safety_block",
    "tools_materials",
    "documents_required",
    "evidence_required",
    "references_body",
    "procedure_body",
    "demo_notes_body",
)
SECTION_BODIES = ("note_html",)


@tagged("post_install", "-at_install")
class TestWholeDocumentBodies(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("fr_CA")

    def _assert_whole_document(self, model, fnames):
        for fname in fnames:
            field = self.env[model]._fields[fname]
            self.assertEqual(field.type, "html", f"{model}.{fname} must be an Html field")
            self.assertIs(
                field.translate, True,
                f"{model}.{fname} is translated term-by-term (sanitize=True turns "
                "translate=True into html_translate); it must stay sanitize=False so "
                "each language holds its own whole document.",
            )
            self.assertFalse(
                field.sanitize,
                f"{model}.{fname} must keep sanitize=False (see module docstring).",
            )

    def test_competency_bodies_are_whole_documents(self):
        self._assert_whole_document("cbet.competency", COMPETENCY_BODIES)

    def test_job_aid_section_note_is_whole_document(self):
        self._assert_whole_document("cbet.job.aid.section", SECTION_BODIES)

    def test_writing_one_language_keeps_the_other(self):
        comp = self.env["cbet.competency"].with_user(self.manager).create({
            "code": "XWD-01",
            "name": "Whole document guard",
        })
        en = "<h2>Steps</h2><ol><li>Open the lid.</li><li>Check the seal.</li></ol>"
        fr = ("<h2>Étapes</h2><p>Avant tout : lire la fiche.</p>"
              "<ul><li>Ouvrir le couvercle.</li></ul><table><tr><td>Note</td></tr></table>")
        comp.with_context(lang="en_US").write({"procedure_body": en})
        comp.with_context(lang="fr_CA").write({"procedure_body": fr})
        comp.invalidate_recordset()
        self.assertEqual(comp.with_context(lang="en_US").procedure_body, en)
        self.assertEqual(comp.with_context(lang="fr_CA").procedure_body, fr)
        # And the other way round: an English rewrite leaves the French alone.
        en2 = "<p>Single paragraph, different structure.</p>"
        comp.with_context(lang="en_US").write({"procedure_body": en2})
        comp.invalidate_recordset()
        self.assertEqual(comp.with_context(lang="en_US").procedure_body, en2)
        self.assertEqual(comp.with_context(lang="fr_CA").procedure_body, fr)
