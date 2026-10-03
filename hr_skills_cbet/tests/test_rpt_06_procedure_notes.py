"""UC-RPT-06 — the procedure and the trainer's demonstration notes as PDFs.

AC1: the procedure report prints the header and the stored procedure body.
AC2: the demo-notes report prints the header, the stored body and ends with a
     blank per-session log of eight rows (Date | Technician | Notes).
AC3: the language of the rendering context picks the language of the body
     and of the labels.
AC4: a draft competency prints the watermark on both documents.
"""
from odoo.tests.common import tagged

from .common import CbetCommon

WATERMARK = 'class="cbet-watermark"'

PROCEDURE = "hr_skills_cbet.action_report_cbet_procedure"
NOTES = "hr_skills_cbet.action_report_cbet_demo_notes"


@tagged("post_install", "-at_install")
class TestRptProcedureNotes(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comp = cls._make_full_competency("XPR-01")

    def test_procedure_prints_the_body(self):
        html = self._render(PROCEDURE, self.comp)
        self.assertIn("XPR-01", html)
        self.assertIn("Read the synthetic bench", html)
        self.assertIn("Procedure", html)
        self.assertIn(self.FULL_FICHE["procedure_body"], html)
        self.assertNotIn(WATERMARK, html)
        report = self.env.ref(PROCEDURE)
        self.assertEqual(self.env["ir.actions.report"]._cbet_print_name(report, self.comp),
                         "procedure_XPR-01_v1.0")

    def test_demo_notes_end_with_blank_log(self):
        html = self._render(NOTES, self.comp)
        self.assertIn(self.FULL_FICHE["demo_notes_body"], html)
        self.assertIn("Trainer's notes (per session)", html)
        self.assertEqual(html.count("cbet-log-row"), 8)
        for col in ("Date", "Technician", "Notes"):
            self.assertIn(col, html)
        self.assertGreater(html.index("cbet-log-row"), html.index("Step 1 — Prepare"))
        report = self.env.ref(NOTES)
        self.assertEqual(self.env["ir.actions.report"]._cbet_print_name(report, self.comp),
                         "demo_notes_XPR-01_v1.0")

    def test_empty_bodies_print_na(self):
        bare = self._make_competency("XPR-02")
        self.assertIn("N/A", self._render(PROCEDURE, bare))
        html = self._render(NOTES, bare)
        self.assertIn("N/A", html)
        self.assertEqual(html.count("cbet-log-row"), 8)

    def test_language_switch(self):
        lang = self._load_fr()
        fr_body = "<h2>Étapes</h2><ol><li>Isoler le banc.</li></ol>"
        self.comp.with_context(lang=lang).write({"procedure_body": fr_body})
        self.comp.invalidate_recordset()
        fr = self._render(PROCEDURE, self.comp, lang=lang)
        self.assertIn(fr_body, fr)
        self.assertNotIn(self.FULL_FICHE["procedure_body"], fr)
        self.assertIn("Procédure", fr)
        en = self._render(PROCEDURE, self.comp, lang="en_US")
        self.assertIn(self.FULL_FICHE["procedure_body"], en)
        self.assertNotIn(fr_body, en)
        notes_fr = self._render(NOTES, self.comp, lang=lang)
        self.assertIn("Notes du formateur (par session)", notes_fr)
        self.assertIn("Technicien", notes_fr)

    def test_draft_watermark(self):
        draft = self._make_full_competency("XPR-03", publish=False)
        self.assertIn(WATERMARK, self._render(PROCEDURE, draft))
        self.assertIn(WATERMARK, self._render(NOTES, draft))
