"""UC-RPT-03 — the competency fiche as a PDF report.

AC1: the fiche reproduces the 14 numbered sections of the vault template, in
     order, under a header that carries code, name, version and publish date.
AC2: §8 criteria, §9 protocol, §10 evaluator, §12 validity and §13 meta come
     from the structured fields (not from stored html); the pass rule names the
     competency's own threshold.
AC3: an empty section prints the N/A marker instead of disappearing.
AC4: rendering in French flips the section headings and labels.
AC5: a draft competency prints a DRAFT watermark; a published one does not.
"""
from odoo.tests.common import tagged

from .common import CbetCommon

WATERMARK = 'class="cbet-watermark"'

REPORT = "hr_skills_cbet.action_report_cbet_fiche"

EN_TITLES = [
    "1. Execution context",
    "2. Prerequisites",
    "3. Underlying knowledge",
    "4. Safety",
    "5. Required tools and materials",
    "6. Documents required on site",
    "7. Procedure / quick reference",
    "8. Measurable performance criteria",
    "9. Assessment protocol",
    "10. Qualified evaluator",
    "11. Records to retain",
    "12. Validity and recertification",
    "13. Meta — for the trainer",
    "14. References",
]


@tagged("post_install", "-at_install")
class TestRptFiche(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comp = cls._make_full_competency("XPR-01")

    def _positions(self, html, needles):
        positions = []
        for needle in needles:
            self.assertIn(needle, html, "missing section heading %r" % needle)
            positions.append(html.index(needle))
        return positions

    def test_fourteen_sections_in_order(self):
        html = self._render(REPORT, self.comp)
        positions = self._positions(html, EN_TITLES)
        self.assertEqual(positions, sorted(positions), "fiche sections out of order")

    def test_header_carries_identity_and_version(self):
        html = self._render(REPORT, self.comp)
        self.assertIn("XPR-01", html)
        self.assertIn("Read the synthetic bench", html)
        self.assertIn(self.FULL_FICHE["subtitle"], html)
        self.assertIn("Test domain", html)
        self.assertIn("1.0", html)
        self.assertIn(self.comp.publish_date.strftime("%m/%d/%Y"), html)
        self.assertIn("Competency sheet", html)

    def test_html_sections_are_the_stored_bodies(self):
        html = self._render(REPORT, self.comp)
        for body in ("execution_context", "knowledge_body", "safety_block",
                     "tools_materials", "documents_required", "evidence_required",
                     "references_body"):
            self.assertIn(self.FULL_FICHE[body], html, body)

    def test_prerequisites_table_from_edges(self):
        html = self._render(REPORT, self.comp)
        self.assertIn("XPQ-01", html)
        self.assertIn("Safe isolation of a bench", html)
        self.assertIn("Mandatory", html)

    def test_generated_documents_line(self):
        html = self._render(REPORT, self.comp)
        self.assertIn("Generated documents", html)
        self.assertIn("Procedure", html)
        self.assertIn("Job aid", html)
        self.assertIn("Demonstration notes", html)

    def test_criteria_from_structured_fields(self):
        html = self._render(REPORT, self.comp)
        for text in ("Bench isolated before opening", "Readings within tolerance",
                     "Data recorded on the form"):
            self.assertIn(text, html)
        # Typed markers come from the Selection labels.
        self.assertIn("🔒", html)
        self.assertIn("⚠️", html)
        self.assertIn("▫️", html)
        # The pass rule quotes the competency's own threshold.
        self.comp.pass_threshold = 75.0
        html = self._render(REPORT, self.comp)
        self.assertIn("75", html)
        self.assertIn("Pass/fail rule", html)

    def test_protocol_from_structured_fields(self):
        html = self._render(REPORT, self.comp)
        self.assertIn("Demonstration on the test bench", html)
        self.assertIn("Training room", html)
        self.assertIn("~45 min", html)          # 0.75 h
        self.assertIn("Bench in service", html)
        self.assertIn("Written procedure allowed, no verbal help", html)
        self.assertIn("Explain each key step aloud", html)
        # §10
        self.assertIn("Designated trainer", html)
        self.assertIn("Preferably not the candidate", html)
        # §12
        self.assertIn("24 months", html)
        self.assertIn("At least 3 interventions", html)
        self.assertIn("Light demonstration", html)
        self.assertIn("Incident or major procedure change", html)
        # §13
        self.assertIn("★★★ — frequent", html)
        self.assertIn("Medium", html)
        self.assertIn("2 h demo + 4 h supervised practice", html)
        self.assertIn("Confuses the inlet with the outlet", html)

    def test_empty_sections_print_na(self):
        bare = self._make_competency("XPR-02", name="Bare competency")
        html = self._render(REPORT, bare)
        positions = self._positions(html, EN_TITLES)
        self.assertEqual(positions, sorted(positions))
        # Every html body, the prerequisites, the criteria, the protocol, the
        # evaluator, the meta and the references are empty: the marker shows
        # up at least once per empty section.
        self.assertGreaterEqual(html.count("N/A"), 10)
        full = self._render(REPORT, self.comp)
        self.assertLess(full.count("N/A"), html.count("N/A"))

    def test_french_rendering_flips_headings(self):
        lang = self._load_fr()
        fr = self._render(REPORT, self.comp, lang=lang)
        self.assertIn("8. Critères de performance mesurables", fr)
        self.assertIn("13. Méta — pour le formateur", fr)
        self.assertIn("Fiche de compétence", fr)
        self.assertIn("Obligatoire", fr)
        self.assertNotIn("8. Measurable performance criteria", fr)
        en = self._render(REPORT, self.comp, lang="en_US")
        self.assertIn("8. Measurable performance criteria", en)
        self.assertNotIn("Critères de performance mesurables", en)

    def test_draft_watermark(self):
        import base64
        import re
        draft = self._make_full_competency("XPR-03", publish=False)
        self.assertEqual(draft.state, "draft")
        html = self._render(REPORT, draft)
        self.assertIn(WATERMARK, html)
        # The stamp is a tiled SVG background carrying the bilingual mark.
        uri = re.search(r"base64,([A-Za-z0-9+/=]+)", html.split(WATERMARK, 1)[1]).group(1)
        self.assertIn("BROUILLON / DRAFT", base64.b64decode(uri).decode())
        self.assertNotIn(WATERMARK, self._render(REPORT, self.comp))

    def test_print_report_name(self):
        report = self.env.ref(REPORT)
        self.assertEqual(report.paperformat_id,
                         self.env.ref("hr_skills_cbet.paperformat_cbet_letter"))
        self.assertEqual(report.paperformat_id.format, "Letter")
        name = self.env["ir.actions.report"]._cbet_print_name(report, self.comp)
        self.assertEqual(name, "fiche_XPR-01_v1.0")
