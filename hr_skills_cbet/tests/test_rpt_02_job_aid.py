"""UC-RPT-02 — the field job aid (aide-mémoire) as a recto/verso PDF.

AC1: page 1 prints the recto blocks in order (icon + name, lines), then a page
     break, then the verso checklist with one ☐ per line; reference tables
     (note_html) print under their section.
AC2: a line's icon prints as the catalog SVG (shipped with the module), else
     as the emoji text when the icon has none.
AC3: a variant job aid carries its variant in the title and in the file name.
AC4: the draft watermark follows the competency's state.
AC5 (19.0.1.12.0, field card): the job aid prints in its own one-line frame —
     logo + company name, code/title/variant/version — and a code · version ·
     page footer; no company address, tax number, phone, email or website and
     none of the web.external_layout classes; its own Letter paper format.
AC6: recto items print one per line (icon + text), verso items with a drawn
     check box; the body size class follows the card's line count (l/m/s).
"""
import base64

from odoo import Command
from odoo.tests.common import tagged

from .common import CbetCommon

WATERMARK = 'class="cbet-watermark"'
PAGE_BREAK = 'class="cbet-page-break"'

REPORT = "hr_skills_cbet.action_report_cbet_job_aid"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
# A 1x1 transparent PNG — the smallest logo wkhtmltopdf would print.
PNG_1PX = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="


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
        # Recto lines print one per line, verso lines carry a drawn check box.
        self.assertIn("safety glasses", html)
        self.assertIn("Bench under pressure — point, do not touch", html)
        self.assertGreaterEqual(html.count('class="cbet-box"'), 2)
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
        # The frame prints in French too, with the same minimal content.
        self.assertIn('class="header cbet-ja-header"', fr)
        self.assertIn('class="footer cbet-ja-footer"', fr)
        self.assertIn(self.env.company.name, fr)

    # ------------------------------------------------------- field card frame
    def _letterhead_company(self):
        self.env.company.write({
            "name": "Synthetic Water Inc.",
            "logo": PNG_1PX,
            "street": "123 Rue du Banc",
            "city": "Montréal",
            "zip": "H1A 1A1",
            "phone": "+1 514 555 0199",
            "email": "info@synthetic-water.example",
            "website": "https://synthetic-water.example",
            "vat": "123456789RT0001",
            "report_header": "Water you can trust",
            "report_footer": "Synthetic Water Inc. — 123 Rue du Banc — +1 514 555 0199",
        })
        return self.env.company

    def test_frame_is_logo_name_and_identity_only(self):
        company = self._letterhead_company()
        html = self._render(REPORT, self.aid)
        # Own frame, not the company letterhead.
        self.assertIn('class="header cbet-ja-header"', html)
        self.assertIn('class="footer cbet-ja-footer"', html)
        self.assertNotIn("o_company_", html)
        self.assertNotIn("o_report_layout_", html)
        self.assertNotIn("external_layout", html)
        # Logo (data URI) + company name, the card identity.
        header = html.split('class="header cbet-ja-header"', 1)[1].split('class="article', 1)[0]
        self.assertIn('<img', header)
        self.assertIn("data:image/png;base64,", header)
        self.assertIn("Synthetic Water Inc.", header)
        self.assertIn("XPR-01", header)
        self.assertIn("Read the synthetic bench", header)
        self.assertIn("v1.0", header)
        # The body is the article Odoo's PDF splitter expects.
        self.assertIn('class="article cbet-ja-article" data-oe-model="cbet.job.aid"', html)
        self.assertIn('data-oe-id="%s"' % self.aid.id, html)
        # Footer: code · version · page counter, nothing else.
        footer = html.split('class="footer cbet-ja-footer"', 1)[1].split("</div>", 1)[0]
        self.assertIn("XPR-01", footer)
        self.assertIn("v1.0", footer)
        self.assertIn('<span class="page"', footer)
        self.assertIn('<span class="topage"', footer)
        # Nothing of the letterhead anywhere in the document.
        for noise in (company.street, company.city, company.zip, company.phone,
                      company.email, company.website, company.vat,
                      "Water you can trust", "Tax ID"):
            self.assertNotIn(noise, html, noise)
        self.assertNotIn("Rue du Banc", html)

    def test_variant_in_frame(self):
        ro = self._make_job_aid(self.comp, variant="RO")
        html = self._render(REPORT, ro)
        header = html.split('class="header cbet-ja-header"', 1)[1].split('class="article', 1)[0]
        self.assertIn("[<span>RO</span>]", header)
        footer = html.split('class="footer cbet-ja-footer"', 1)[1].split("</div>", 1)[0]
        self.assertIn("[<span>RO</span>]", footer)

    def test_own_paper_format(self):
        report = self.env.ref(REPORT)
        fmt = self.env.ref("hr_skills_cbet.paperformat_cbet_job_aid")
        self.assertEqual(report.paperformat_id, fmt)
        self.assertEqual(fmt.format, "Letter")
        self.assertEqual(fmt.orientation, "Portrait")
        self.assertEqual((fmt.margin_left, fmt.margin_right), (10, 10))
        # The one-line header lives in the top margin: 12 mm of room above
        # the content, which starts at 22 mm.
        self.assertEqual((fmt.margin_top, fmt.header_spacing), (22, 12))
        self.assertFalse(fmt.header_line)
        # Printed at nominal size (wkhtmltopdf's smart shrinking scales a
        # page by ~0.84 otherwise).
        self.assertTrue(fmt.disable_shrinking)
        # The other documents keep the letterhead paper format.
        for xmlid in ("hr_skills_cbet.action_report_cbet_fiche",
                      "hr_skills_cbet.action_report_cbet_procedure",
                      "hr_skills_cbet.action_report_cbet_demo_notes"):
            self.assertEqual(self.env.ref(xmlid).paperformat_id,
                             self.env.ref("hr_skills_cbet.paperformat_cbet_letter"), xmlid)

    def test_draft_watermark_in_the_card_frame(self):
        self._letterhead_company()
        self.comp.with_user(self.manager).action_reset_to_draft()
        html = self._render(REPORT, self.aid)
        self.assertIn(WATERMARK, html)
        self.assertNotIn("o_company_", html)

    # ------------------------------------------------------- scale to the page
    def test_recto_items_one_per_line(self):
        html = self._render(REPORT, self.aid)
        ppe = html.split("PPE</span>", 1)[1].split("STOP — escalate", 1)[0]
        self.assertEqual(ppe.count('<li class="cbet-item">'), 2)
        self.assertNotIn(" · ", ppe)
        self.assertNotIn('class="cbet-inline"', html)
        data = html.split("Data to record</span>", 1)[1].split(PAGE_BREAK, 1)[0]
        self.assertEqual(data.count('<li class="cbet-item">'), 2)
        # Verso: a drawn 7 mm box per item, the icon hanging next to it.
        verso = html.split(PAGE_BREAK, 1)[1]
        self.assertRegex(verso, r'<li class="cbet-check-item">\s*<span class="cbet-box"')
        self.assertIn('class="cbet-check-item cbet-has-icon"', verso)
        self.assertIn("width: 7mm; height: 7mm", html)
        self.assertIn(".cbet-ja h2 .cbet-icon { height: 8mm; width: 8mm;", html)
        self.assertIn("height: 6mm; width: 6mm; margin: 0; }", html)
        self.assertIn(".cbet-ja h2 { font-size: 16pt;", html)
        self.assertIn(".cbet-ja-l { font-size: 13pt; }", html)
        self.assertIn(".cbet-ja-m { font-size: 12pt; }", html)
        self.assertIn(".cbet-ja-s { font-size: 11pt; }", html)
        self.assertIn(".cbet-ja-xs { font-size: 10pt; }", html)

    def _card(self, code, recto_lines, verso_lines, text="Do the thing — keep both hands clear of the moving parts",
              recto_sections=1, note_rows=0, icon=None):
        """A synthetic card: ``recto_lines`` items spread over ``recto_sections``
        recto blocks, ``verso_lines`` check items in one phase (with a
        ``note_rows``-row reference table)."""
        comp = self._make_full_competency(code)
        note = ""
        if note_rows:
            note = "<table>%s</table>" % "".join(
                "<tr><td>Row %s</td><td>value</td></tr>" % i for i in range(note_rows))
        per_section = [recto_lines // recto_sections] * recto_sections
        per_section[0] += recto_lines - sum(per_section)
        line = lambda: Command.create({"text": text, "icon_id": icon and icon.id})
        return self.env["cbet.job.aid"].create({
            "competency_id": comp.id,
            "section_ids": [
                Command.create({
                    "face": "recto", "kind": "tools", "name": "Block %s" % i,
                    "line_ids": [line() for _i in range(n)],
                }) for i, n in enumerate(per_section)
            ] + [
                Command.create({
                    "face": "verso", "kind": "phase", "name": "1. Phase",
                    "line_ids": [line() for _i in range(verso_lines)],
                    "note_html": note,
                }),
            ],
        })

    def _classes(self):
        from odoo.addons.hr_skills_cbet.report import cbet_document_report as m
        return [c for c, _metrics in m.JOB_AID_SIZE_CLASSES], m.JOB_AID_PAGE_MM

    def test_size_class_is_the_largest_that_fits_both_faces(self):
        fmt = self.env["cbet.document.report"]
        classes, page = self._classes()
        self.assertEqual(classes, ["l", "m", "s", "xs"])
        # A short card prints large, a long one small, in between the
        # chosen class is the largest in which both faces fit the page.
        short = self._card("XSZ-01", 4, 4)
        self.assertEqual(fmt._job_aid_size_class(short), "l")
        self.assertIn('class="page cbet-doc cbet-jobaid cbet-ja cbet-ja-l"', self._render(REPORT, short))
        long_ = self._card("XSZ-02", 40, 40)
        self.assertEqual(fmt._job_aid_size_class(long_), "xs")
        self.assertIn("cbet-ja cbet-ja-xs", self._render(REPORT, long_))
        previous = 0
        for n in (10, 20, 24, 26, 28, 30, 32, 34, 36):
            card = self._card("XSZ-%02d" % n, n, 4, recto_sections=2)
            chosen = fmt._job_aid_size_class(card)
            rank = classes.index(chosen)
            self.assertGreaterEqual(rank, previous, "a longer card never prints larger (%s items)" % n)
            previous = rank
            fits = lambda c: all(fmt._job_aid_face_height(card, f, c) <= page for f in ("recto", "verso"))
            if chosen != "xs":
                self.assertTrue(fits(chosen), chosen)
            if rank:
                self.assertFalse(fits(classes[rank - 1]), "%s items: %s would fit" % (n, classes[rank - 1]))
        # Both ends of the sweep are reached.
        self.assertEqual(fmt._job_aid_size_class(self._card("XSZ-98", 10, 4, recto_sections=2)), "l")
        self.assertEqual(fmt._job_aid_size_class(self._card("XSZ-99", 36, 4, recto_sections=2)), "xs")

    def test_verso_boxes_drive_the_class_too(self):
        fmt = self.env["cbet.document.report"]
        # 4 recto items but 30 check items: the verso's 7 mm boxes do not fit
        # a page at the large sizes.
        card = self._card("XSZ-40", 4, 30)
        self.assertLess(fmt._job_aid_face_height(card, "recto", "l"), 100)
        self.assertGreater(fmt._job_aid_face_height(card, "verso", "l"), self._classes()[1])
        self.assertIn(fmt._job_aid_size_class(card), ("s", "xs"))
        # A wrapped check item grows past its box, an icon narrows its column.
        wide = self._card("XSZ-41", 4, 10, text="x" * 150)
        self.assertGreater(fmt._job_aid_face_height(wide, "verso", "l"),
                           fmt._job_aid_face_height(self._card("XSZ-42", 4, 10), "verso", "l"))
        stop = self.env["cbet.icon"]._by_token()["sev-stop"]
        plain = self._card("XSZ-43", 4, 10, text="y" * 78)
        iconed = self._card("XSZ-44", 4, 10, text="y" * 78, icon=stop)
        self.assertGreater(fmt._job_aid_face_height(iconed, "verso", "l"),
                           fmt._job_aid_face_height(plain, "verso", "l"))

    def test_short_items_print_in_two_columns(self):
        fmt = self.env["cbet.document.report"]
        short = self._card("XSZ-50", 6, 2, text="safety shoes")
        long_ = self._card("XSZ-51", 6, 2)
        block_short = short._face_sections("recto")[0]
        block_long = long_._face_sections("recto")[0]
        self.assertTrue(fmt._job_aid_two_columns(block_short, "l"))
        self.assertFalse(fmt._job_aid_two_columns(block_long, "l"))
        # Two columns need at least three items; STOP blocks stay stacked.
        self.assertFalse(fmt._job_aid_two_columns(self._card("XSZ-52", 2, 2, text="shoes")._face_sections("recto")[0], "l"))
        block_short.kind = "stop"
        self.assertFalse(fmt._job_aid_two_columns(block_short, "l"))
        block_short.kind = "ppe"
        # The half column widens as the body shrinks: a 42-character item is
        # too long for it at 13 pt, fine at 11 pt.
        mid = self._card("XSZ-53", 4, 2, text="x" * 42)._face_sections("recto")[0]
        self.assertFalse(fmt._job_aid_two_columns(mid, "l"))
        self.assertTrue(fmt._job_aid_two_columns(mid, "s"))
        # Rendered as a two-column list, one item per <li>; half the height.
        html = self._render(REPORT, short)
        self.assertIn('<ul class="cbet-items cbet-2col">', html)
        self.assertEqual(html.count('<li class="cbet-item">'), 6)
        self.assertNotIn('<ul class="cbet-items cbet-2col">', self._render(REPORT, long_))
        self.assertLess(fmt._job_aid_face_height(short, "recto", "l"),
                        fmt._job_aid_face_height(long_, "recto", "l"))

    def test_reference_tables_and_wrapping_count(self):
        fmt = self.env["cbet.document.report"]
        plain = self._card("XSZ-60", 4, 4)
        tabled = self._card("XSZ-61", 4, 4, note_rows=6)
        self.assertGreater(fmt._job_aid_face_height(tabled, "verso", "l"),
                           fmt._job_aid_face_height(plain, "verso", "l") + 6 * 5)
        self.assertEqual(fmt._job_aid_lines(plain), {"recto": 5, "verso": 5, "total": 10})
        self.assertEqual(fmt._job_aid_lines(tabled), {"recto": 5, "verso": 11, "total": 16})
        # Long data lines wrap on the card: a 150-character item counts twice.
        wide = self._card("XSZ-62", 10, 10, text="x" * 150)
        self.assertEqual(fmt._job_aid_lines(wide), {"recto": 21, "verso": 21, "total": 42})
        self.assertGreater(fmt._job_aid_face_height(wide, "recto", "l"),
                           fmt._job_aid_face_height(self._card("XSZ-63", 10, 10), "recto", "l"))
        # A long title wraps and costs a line of the recto.
        titled = self._card("XSZ-64", 4, 4)
        before = fmt._job_aid_face_height(titled, "recto", "l")
        titled.competency_id.name = "A much longer competency name that wraps on the card title line"
        self.assertGreater(fmt._job_aid_face_height(titled, "recto", "l"), before)

    def test_forced_size_class(self):
        fmt = self.env["cbet.document.report"]
        short = self._card("XSZ-70", 4, 4)
        self.assertEqual(fmt._job_aid_size_class(short), "l")
        self.assertEqual(fmt.with_context(cbet_job_aid_size_class="xs")._job_aid_size_class(short), "xs")
        self.assertEqual(fmt.with_context(cbet_job_aid_size_class="huge")._job_aid_size_class(short), "l")
        html = self._render(REPORT.replace("action_report_cbet_job_aid", "action_report_cbet_job_aid"), short)
        self.assertIn("cbet-ja-l", html)
        Report = self.env["ir.actions.report"].with_context(cbet_job_aid_size_class="s")
        html, _type = Report._render_qweb_html(REPORT, short.ids)
        self.assertIn("cbet-ja cbet-ja-s", html.decode())
