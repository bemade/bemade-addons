"""UC-CAT-15 — the job-aid icon set: every catalog token ships its own SVG.

AC1: after install every active cbet.icon carries a non-empty SVG, which is the
     module's own static/src/img/icons/<token>.svg (svg_filename set).
AC2: each SVG is hygienic: well-formed XML rooted on <svg> with a 24×24
     viewBox, no <script>, no external href / xlink:href, no raster, no text,
     at most 2 KB; _svg_data_uri() yields a printable data URI.
AC3: the icon legend report renders every token grouped by category, from a
     selection or (no record) for the whole active catalog.
AC4: the job aid prints the SVG pictograms and no emoji stand-in for the
     seeded tokens.
"""
import base64
import xml.etree.ElementTree as ET

from odoo.tests.common import tagged
from odoo.tools.misc import file_open

from .common import CbetCommon

LEGEND = "hr_skills_cbet.action_report_cbet_icon_legend"
JOB_AID = "hr_skills_cbet.action_report_cbet_job_aid"
SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
MAX_BYTES = 2048
# Tokens per category as seeded (epi 9, sev 6, act 10, outil 16, item 9, comp 5).
EXPECTED = {"epi": 9, "sev": 6, "act": 10, "outil": 16, "item": 9, "comp": 5}


@tagged("post_install", "-at_install")
class TestCatIcons(CbetCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.icons = cls.env["cbet.icon"].search([])

    def _raw(self, icon):
        return base64.b64decode(icon.with_context(bin_size=False).svg)

    def test_catalog_is_complete(self):
        counts = {}
        for icon in self.icons:
            counts[icon.category] = counts.get(icon.category, 0) + 1
        self.assertEqual(counts, EXPECTED)
        self.assertEqual(len(self.icons), sum(EXPECTED.values()))

    def test_every_active_icon_has_its_static_svg(self):
        for icon in self.icons:
            with self.subTest(token=icon.token):
                self.assertTrue(icon.svg, "no SVG on %s" % icon.token)
                self.assertEqual(icon.svg_filename, icon.token + ".svg")
                with file_open("hr_skills_cbet/static/src/img/icons/%s.svg" % icon.token, "rb") as f:
                    self.assertEqual(self._raw(icon), f.read())

    def test_svg_hygiene(self):
        for icon in self.icons:
            with self.subTest(token=icon.token):
                raw = self._raw(icon)
                self.assertLessEqual(len(raw), MAX_BYTES)
                root = ET.fromstring(raw)
                self.assertEqual(root.tag, SVG_NS + "svg")
                self.assertEqual(root.get("viewBox", "").split(), ["0", "0", "24", "24"])
                self.assertEqual(root.get("role"), "img")
                self.assertIsNotNone(root.find(SVG_NS + "title"))
                for el in root.iter():
                    tag = el.tag.replace(SVG_NS, "")
                    self.assertNotIn(tag, ("script", "image", "foreignObject", "text", "use", "style"),
                                     "%s in %s" % (tag, icon.token))
                    for attr in ("href", XLINK_HREF):
                        self.assertIsNone(el.get(attr), "%s carries %s" % (icon.token, attr))
                    for name in el.attrib:
                        self.assertFalse(name.startswith("on"), "event handler in %s" % icon.token)
                    self.assertNotIn("url(", (el.get("fill") or "") + (el.get("stroke") or ""))

    def test_data_uri_is_printable(self):
        for icon in self.icons:
            uri = icon._svg_data_uri()
            self.assertTrue(uri.startswith("data:image/svg+xml;base64,"), icon.token)
            printed = base64.b64decode(uri.split("base64,")[1]).decode()
            root = ET.fromstring(printed)
            # An intrinsic size: wkhtmltopdf draws nothing for a viewBox-only SVG.
            self.assertTrue(root.get("width") and root.get("height"), icon.token)

    def test_legend_report_groups_every_token(self):
        html = self._render(LEGEND, self.icons)
        for icon in self.icons:
            self.assertIn(icon.token, html)
            self.assertIn(icon._svg_data_uri(), html)
        self.assertNotIn('class="cbet-icon-emoji"', html)
        # the emoji stand-ins are catalog data, not print material: wkhtmltopdf
        # draws most of them as boxes, so the legend does not print them
        self.assertNotIn("<th>Emoji</th>", html)
        self.assertNotIn('class="c-emoji"', html)
        labels = dict(self.icons._fields["category"]._description_selection(self.env))
        positions = [html.index("<h2>%s</h2>" % labels[c]) for c in ("epi", "sev", "act", "outil", "item", "comp")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("Icon legend", html)
        # A selection prints only itself.
        epi = self.icons.filtered(lambda i: i.category == "epi")
        html = self._render(LEGEND, epi)
        self.assertNotIn("sev-stop", html)
        self.assertIn("epi-lunettes", html)

    def test_legend_report_without_records_prints_the_catalog(self):
        Report = self.env["ir.actions.report"]
        html, _type = Report._render_qweb_html(LEGEND, [])
        html = html.decode()
        for icon in self.icons:
            self.assertIn(icon.token, html)
        # Archived icons are left out of the catalog print.
        gone = self.icons.filtered(lambda i: i.token == "comp-tete")
        gone.active = False
        html, _type = Report._render_qweb_html(LEGEND, [])
        self.assertNotIn("comp-tete", html.decode())

    def test_legend_report_in_french(self):
        lang = self._load_fr()
        html = self._render(LEGEND, self.icons, lang=lang)
        self.assertIn("Légende des pictogrammes", html)
        self.assertIn("Jeton", html)
        self.assertNotIn("Icon legend", html)

    def test_legend_report_pdf_pipeline(self):
        # Under --test-enable the PDF pipeline hands back the html it would
        # print (a real wkhtmltopdf render is the shell/UAT check).
        out, _type = self.env["ir.actions.report"]._render_qweb_pdf(LEGEND, self.icons.ids)
        self.assertTrue(out.startswith(b"%PDF") or b"cbet-legend" in out)

    def test_uploaded_svg_keeps_an_image_mimetype(self):
        import base64
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24"/></svg>'
        icon = self.icons[0].with_user(self.manager)
        icon.write({"svg": base64.b64encode(svg)})
        att = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", "cbet.icon"), ("res_field", "=", "svg"), ("res_id", "=", icon.id)])
        self.assertEqual(att.mimetype, "image/svg+xml")
        created = self.env["cbet.icon"].with_user(self.manager).create({
            "token": "act-test-upload", "name": "Upload", "category": "act",
            "svg": base64.b64encode(svg)})
        att = self.env["ir.attachment"].sudo().search([
            ("res_model", "=", "cbet.icon"), ("res_field", "=", "svg"), ("res_id", "=", created.id)])
        self.assertEqual(att.mimetype, "image/svg+xml")

    def test_job_aid_prints_svg_not_emoji(self):
        comp = self._make_full_competency("XIC-01")
        aid = self._make_job_aid(comp)
        html = self._render(JOB_AID, aid)
        self.assertNotIn('class="cbet-icon-emoji"', html)
        icons = self.env["cbet.icon"]._by_token()
        for token in ("epi-lunettes", "sev-stop"):
            self.assertIn(icons[token]._svg_data_uri(), html)
            self.assertNotIn(icons[token].emoji, html)
        self.assertGreaterEqual(html.count('class="cbet-icon"'), 5)
