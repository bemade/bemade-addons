"""UC-RPT-02 — the field job aid (aide-mémoire) as a recto/verso PDF.

AC1: page 1 prints the recto blocks in order (icon + name, lines), then a page
     break, then the verso checklist with one ☐ per line; reference tables
     (note_html) print under their section.
AC2: a line's icon prints as the catalog SVG (shipped with the module), else
     as the emoji text when the icon has none.
AC3: a variant job aid carries its variant in the title and in the file name.
AC4: the draft watermark follows the competency's state.
"""
import base64

from odoo.tests.common import tagged

from .common import CbetCommon

WATERMARK = 'class="cbet-watermark"'
PAGE_BREAK = 'class="cbet-page-break"'

REPORT = "hr_skills_cbet.action_report_cbet_job_aid"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'


@tagged("post_install", "-at_install")
class TestRptJobAid(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.comp = cls._make_full_competency("XPR-01")
        cls.aid = cls._make_job_aid(cls.comp)

    def test_recto_then_break_then_verso(self):
        html = self._render(REPORT, self.aid)
        self.assertIn("XPR-01", html)
        self.assertIn("Read the synthetic bench", html)
        recto = [html.index(s) for s in ("PPE", "STOP — escalate", "Data to record")]
        self.assertEqual(recto, sorted(recto))
        brk = html.index(PAGE_BREAK)
        verso = [html.index(s) for s in ("1. State the principle", "2. Check before leaving")]
        self.assertLess(max(recto), brk)
        self.assertLess(brk, min(verso))
        self.assertEqual(verso, sorted(verso))
        self.assertIn("Procedure — checklist", html)
        # Recto lines are joined inline, verso lines are check boxes.
        self.assertIn("safety glasses", html)
        self.assertIn("Bench under pressure — point, do not touch", html)
        self.assertGreaterEqual(html.count("☐"), 2)
        # The reference table prints under its phase.
        self.assertIn("kPa — inlet reading", html)
        self.assertGreater(html.index("kPa — inlet reading"), html.index("2. Check before leaving"))

    def test_icon_emoji_fallback_then_svg(self):
        icons = self.env["cbet.icon"]._by_token()
        goggles, stop = icons["epi-lunettes"], icons["sev-stop"]
        # The catalog ships its SVG set: the job aid prints pictograms.
        self.assertTrue(goggles.svg)
        html = self._render(REPORT, self.aid)
        self.assertIn(goggles._svg_data_uri(), html)
        self.assertNotIn('class="cbet-icon-emoji"', html)
        # Without an SVG the emoji stand-in is printed.
        (goggles + stop).svg = False
        html = self._render(REPORT, self.aid)
        self.assertIn(goggles.emoji, html)
        self.assertNotIn("data:image/svg+xml;base64,", html)
        goggles.svg = base64.b64encode(SVG)
        html = self._render(REPORT, self.aid)
        uri = goggles._svg_data_uri()
        self.assertIn(uri, html)
        self.assertNotIn(goggles.emoji, html)
        # wkhtmltopdf draws nothing for a viewBox-only SVG: the printed copy
        # carries an intrinsic size taken from the viewBox.
        printed = base64.b64decode(uri.split("base64,")[1]).decode()
        self.assertIn('width="10" height="10"', printed)
        self.assertIn("<rect", printed)
        # An SVG that already has a size is printed as is.
        sized = SVG.replace(b"<svg ", b'<svg width="24" height="24" ')
        goggles.svg = base64.b64encode(sized)
        self.assertEqual(goggles._svg_data_uri(),
                         "data:image/svg+xml;base64," + base64.b64encode(sized).decode())
        # The STOP icon still has no svg: its emoji is still printed.
        self.assertIn(icons["sev-stop"].emoji, html)

    def test_variant_in_title_and_file_name(self):
        ro = self._make_job_aid(self.comp, variant="RO")
        html = self._render(REPORT, ro)
        self.assertIn("XPR-01</span> — <span>Read the synthetic bench</span> [RO]", html)
        report = self.env.ref(REPORT)
        Report = self.env["ir.actions.report"]
        self.assertEqual(Report._cbet_print_name(report, ro), "job_aid_XPR-01_RO_v1.0")
        self.assertEqual(Report._cbet_print_name(report, self.aid), "job_aid_XPR-01_v1.0")

    def test_title_follows_the_print_language(self):
        self.env["res.lang"]._activate_lang("fr_CA")
        self.comp.with_context(lang="fr_CA").write({"name": "Nom français"})
        html_en = self._render(REPORT, self.aid, lang="en_US")
        html_fr = self._render(REPORT, self.aid, lang="fr_CA")
        self.assertIn("Nom français", html_fr)
        self.assertNotIn("Nom français", html_en)
        self.assertIn(self.comp.with_context(lang="en_US").name, html_en)

    def test_draft_watermark_follows_competency_state(self):
        self.assertNotIn(WATERMARK, self._render(REPORT, self.aid))
        self.comp.with_user(self.manager).action_reset_to_draft()
        self.assertIn(WATERMARK, self._render(REPORT, self.aid))

    def test_french_rendering(self):
        lang = self._load_fr()
        fr = self._render(REPORT, self.aid, lang=lang)
        self.assertIn("Procédure — checklist", fr)
        self.assertIn("Aide-mémoire terrain", fr)
        self.assertNotIn("Procedure — checklist", fr)
