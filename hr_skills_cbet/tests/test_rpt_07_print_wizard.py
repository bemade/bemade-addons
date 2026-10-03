"""UC-RPT-07 — the "Print documents" wizard.

AC1: opened on competencies, the wizard proposes those competencies, the
     user's language and every document kind that exists for them.
AC2: one document kind for one competency downloads a single PDF named after
     the document; several documents download one zip holding one PDF each.
AC3: the chosen language drives the rendering (French output in French).
AC4: asking for nothing raises a clear error.
"""
import io
import zipfile

from odoo.exceptions import UserError
from odoo.tests.common import tagged
from odoo.tools.misc import mute_logger

from .common import CbetCommon


@tagged("post_install", "-at_install")
class TestRptPrintWizard(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comp = cls._make_full_competency("XPR-01")
        cls._make_job_aid(cls.comp)
        cls._make_job_aid(cls.comp, variant="RO")
        cls.bare = cls._make_competency("XPR-02", name="Bare competency")

    def _wizard(self, comps, **vals):
        Wizard = self.env["cbet.print.wizard"].with_user(self.manager).with_context(
            active_model="cbet.competency", active_ids=comps.ids)
        return Wizard.create(vals)

    def _attachment(self, action):
        self.assertEqual(action["type"], "ir.actions.act_url")
        att_id = int(action["url"].split("/web/content/")[1].split("?")[0])
        return self.env["ir.attachment"].browse(att_id)

    def test_defaults_from_active_competencies(self):
        wiz = self._wizard(self.comp)
        self.assertEqual(wiz.competency_ids, self.comp)
        self.assertEqual(wiz.lang, self.manager.lang)
        self.assertTrue(wiz.print_fiche)
        self.assertTrue(wiz.print_procedure)
        self.assertTrue(wiz.print_job_aid)
        self.assertTrue(wiz.print_demo_notes)
        wiz = self._wizard(self.bare)
        self.assertTrue(wiz.print_fiche)
        self.assertFalse(wiz.print_procedure)
        self.assertFalse(wiz.print_job_aid)
        self.assertFalse(wiz.print_demo_notes)

    def test_one_document_is_a_single_pdf(self):
        wiz = self._wizard(self.comp, print_procedure=False, print_job_aid=False,
                           print_demo_notes=False)
        att = self._attachment(wiz.action_print())
        self.assertEqual(att.name, "fiche_XPR-01_v1.0.pdf")
        self.assertEqual(att.mimetype, "application/pdf")
        self.assertTrue(att.raw)

    def test_several_documents_are_zipped(self):
        wiz = self._wizard(self.comp)
        att = self._attachment(wiz.action_print())
        self.assertEqual(att.name, "XPR-01_v1.0_documents.zip")
        self.assertEqual(att.mimetype, "application/zip")
        names = zipfile.ZipFile(io.BytesIO(att.raw)).namelist()
        self.assertEqual(names, [
            "fiche_XPR-01_v1.0.pdf",
            "procedure_XPR-01_v1.0.pdf",
            "job_aid_XPR-01_v1.0.pdf",
            "job_aid_XPR-01_RO_v1.0.pdf",
            "demo_notes_XPR-01_v1.0.pdf",
        ])

    def test_several_competencies_zip_name(self):
        wiz = self._wizard(self.comp | self.bare, print_procedure=False,
                           print_job_aid=False, print_demo_notes=False)
        att = self._attachment(wiz.action_print())
        self.assertEqual(att.name, "cbet_documents.zip")
        names = zipfile.ZipFile(io.BytesIO(att.raw)).namelist()
        self.assertEqual(names, ["fiche_XPR-01_v1.0.pdf", "fiche_XPR-02_v0.1.pdf"])

    def test_language_choice_drives_rendering(self):
        lang = self._load_fr()
        wiz = self._wizard(self.comp, lang=lang, print_procedure=False,
                           print_job_aid=False, print_demo_notes=False)
        att = self._attachment(wiz.action_print())
        # Under --test-enable the report engine hands back the html instead of
        # running wkhtmltopdf, which is what lets the language be checked here.
        if not att.raw.startswith(b"%PDF"):
            html = att.raw.decode()
            self.assertIn("8. Critères de performance mesurables", html)
            self.assertNotIn("8. Measurable performance criteria", html)

    def test_nothing_selected_raises(self):
        wiz = self._wizard(self.comp, print_fiche=False, print_procedure=False,
                           print_job_aid=False, print_demo_notes=False)
        with self.assertRaises(UserError), mute_logger("odoo.sql_db"):
            wiz.action_print()
        # A kind that exists for none of the competencies yields nothing too.
        wiz = self._wizard(self.bare, print_fiche=False, print_procedure=True)
        with self.assertRaises(UserError), mute_logger("odoo.sql_db"):
            wiz.action_print()
