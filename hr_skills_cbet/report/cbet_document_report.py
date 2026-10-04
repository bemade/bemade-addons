import base64
import math
import re

import lxml.html
from lxml import etree

from odoo import api, models
from odoo.tools import is_html_empty
from odoo.tools.mail import html_to_inner_content

# One light, diagonal "BROUILLON / DRAFT" stamp per tile; the tile repeats over
# the whole document, so every printed page carries the mark whatever the
# pagination (wkhtmltopdf neither repeats fixed elements per page nor keeps a
# page-sized tile aligned with its page breaks).
WATERMARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="95mm" height="70mm" viewBox="0 0 95 70">'
    '<text x="47.5" y="38" font-family="Helvetica, Arial, sans-serif" font-size="9" '
    'font-weight="bold" fill="#c00000" fill-opacity="0.13" text-anchor="middle" '
    'transform="rotate(-30 47.5 35)">BROUILLON / DRAFT</text></svg>'
)
WATERMARK_URI = "data:image/svg+xml;base64," + base64.b64encode(WATERMARK_SVG.encode()).decode()

# Field-card size classes (UC-RPT-02). The job aid's typography follows the
# card's content so that a short card fills its two pages and a long one
# stays recto on page 1 / verso on page 2: the largest class whose estimated
# height fits both faces on a Letter page wins. Per class: body size (pt),
# characters per line of the 187 mm text column, and the printed heights in
# mm of a recto item, of one extra wrapped line, of a verso check item (the
# box sets the floor) and of a section heading. Measured on real prints of
# the reference content (19.0.1.12.0, paperformat_cbet_job_aid prints at nominal
# size); the CSS in cbet_job_aid_style mirrors these sizes.
JOB_AID_SIZE_CLASSES = (
    ("l", {"pt": 13, "chars": 80, "column_chars": 36, "item": 7.1, "line": 5.8, "check": 8.1,
           "heading": 13.4, "heading_chars": 52, "heading_line": 7.0, "title_chars": 44}),
    ("m", {"pt": 12, "chars": 87, "column_chars": 40, "item": 6.6, "line": 5.3, "check": 8.0,
           "heading": 13.0, "heading_chars": 52, "heading_line": 7.0, "title_chars": 44}),
    ("s", {"pt": 11, "chars": 95, "column_chars": 44, "item": 6.2, "line": 4.9, "check": 7.0,
           "heading": 12.4, "heading_chars": 52, "heading_line": 7.0, "title_chars": 44}),
    ("xs", {"pt": 10, "chars": 105, "column_chars": 48, "item": 5.7, "line": 4.4, "check": 6.5,
            "heading": 10.7, "heading_chars": 60, "heading_line": 6.0, "title_chars": 52}),
)
JOB_AID_PAGE_MM = 234          # Letter minus the paper format's margins (241), 7 mm safety
JOB_AID_RECTO_TITLE_MM = 22    # kind label + one-line title + meta row
JOB_AID_TITLE_LINE_MM = 8      # each extra line of a long title
JOB_AID_VERSO_TITLE_MM = 9     # "Procedure — checklist"
# A verso item with an icon has a narrower text column (the box, then the icon).
JOB_AID_VERSO_CHARS = 1.0
JOB_AID_VERSO_ICON_CHARS = 0.92
# Recto blocks of several items that all fit the half-width column
# (``column_chars`` of the size class) print in two columns.
JOB_AID_TWO_COLUMN_MIN_ITEMS = 3


def _wrapped_lines(text, chars):
    """Printed lines of a text in a column of ``chars`` characters."""
    return max(1, math.ceil(len(text or "") / chars))


class CbetDocumentReport(models.AbstractModel):
    """Shared rendering helpers of the four training documents (UC-RPT-02/03/06).

    The section headings and the value labels are Python-translated here so
    that a French and an English print of the same competency carry their own
    titles; everything else in the templates is a plain view term.
    """

    _name = "cbet.document.report"
    _description = "CBET training document rendering helpers"

    @api.model
    def _report_values(self, model, docids):
        docs = self.env[model].browse(docids)
        return {
            "doc_ids": docids,
            "doc_model": model,
            "docs": docs,
            "fmt": self,
            "na": self.env._("N/A"),
            "titles": self._section_titles(),
            "watermark_uri": WATERMARK_URI,
        }

    @api.model
    def _section_titles(self):
        _ = self.env._
        return {
            1: _("1. Execution context"),
            2: _("2. Prerequisites"),
            3: _("3. Underlying knowledge (minimum theory required)"),
            4: _("4. Safety"),
            5: _("5. Required tools and materials"),
            6: _("6. Documents required on site"),
            7: _("7. Procedure / quick reference"),
            8: _("8. Measurable performance criteria"),
            9: _("9. Assessment protocol"),
            10: _("10. Qualified evaluator"),
            11: _("11. Records to retain"),
            12: _("12. Validity and recertification"),
            13: _("13. Meta — for the trainer"),
            14: _("14. References"),
        }

    # ------------------------------------------------------------ job aid
    @api.model
    def _job_aid_two_columns(self, section, size_class="l"):
        """Recto blocks of several short items (PPE, tools, data, photos…)
        print in two columns; a block with an item too long for the half
        column of the size class stays in one."""
        texts = [line.text or "" for line in section.line_ids]
        return (section.face == "recto" and section.kind != "stop"
                and len(texts) >= JOB_AID_TWO_COLUMN_MIN_ITEMS
                and max(len(t) for t in texts) <= dict(JOB_AID_SIZE_CLASSES)[size_class]["column_chars"])

    @api.model
    def _job_aid_note_lines(self, html, chars):
        """Printed lines of a reference table / note: its rows and blocks, or
        its text length, whichever is larger."""
        if is_html_empty(html):
            return 0
        html = str(html)
        blocks = len(re.findall(r"<(?:tr|li|p|h[1-3])\b", html))
        text = html_to_inner_content(html)
        return max(1, blocks, math.ceil(len(text) / chars))

    @api.model
    def _job_aid_note_height(self, html, metrics):
        """Estimated printed height (mm) of a reference table / note: each
        table row is as tall as its most wrapped cell (cells share the
        column), plus cell padding and borders; other blocks print as lines."""
        if is_html_empty(html):
            return 0.0
        try:
            root = lxml.html.fromstring("<div>%s</div>" % html)
        except (etree.ParserError, ValueError):
            return self._job_aid_note_lines(html, metrics["chars"]) * metrics["item"]
        height = 0.0
        for table in root.iter("table"):
            height += 3.0
            for row in table.iter("tr"):
                cells = [c for c in row if c.tag in ("td", "th")]
                if not cells:
                    continue
                cell_chars = max(8, metrics["chars"] / len(cells) * 0.85)
                lines = max(_wrapped_lines(c.text_content().strip(), cell_chars) for c in cells)
                height += lines * metrics["line"] + 3.0
        for block in root.iter("p", "li", "h1", "h2", "h3", "blockquote"):
            if any(a.tag == "table" for a in block.iterancestors()):
                continue
            height += _wrapped_lines(block.text_content().strip(), metrics["chars"]) * metrics["line"] + 1.0
        if not height:
            height = self._job_aid_note_lines(html, metrics["chars"]) * metrics["item"]
        return height

    @api.model
    def _job_aid_face_height(self, aid, face, size_class):
        """Estimated printed height (mm) of one face of the card in a size class."""
        metrics = dict(JOB_AID_SIZE_CLASSES)[size_class]
        chars = metrics["chars"]
        if face == "recto":
            title = "%s — %s%s" % (aid.competency_id.code, aid.competency_id.name or "",
                                   " [%s]" % aid.variant if aid.variant else "")
            extra_title_lines = _wrapped_lines(title, metrics["title_chars"]) - 1
            height = JOB_AID_RECTO_TITLE_MM + extra_title_lines * JOB_AID_TITLE_LINE_MM
        else:
            height = JOB_AID_VERSO_TITLE_MM
        for section in aid._face_sections(face):
            height += metrics["heading"]
            height += (_wrapped_lines(section.name, metrics["heading_chars"]) - 1) * metrics["heading_line"]
            lines = section.line_ids
            if face == "verso":
                # The box sets the floor; a wrapped item grows past it.
                for line in lines:
                    factor = JOB_AID_VERSO_ICON_CHARS if line.icon_id else JOB_AID_VERSO_CHARS
                    n = _wrapped_lines(line.text, chars * factor)
                    height += max(metrics["check"], n * metrics["line"] + 1.1)
            else:
                rows = math.ceil(len(lines) / 2) if self._job_aid_two_columns(section, size_class) else len(lines)
                height += rows * metrics["item"]
                height += sum(_wrapped_lines(line.text, chars) - 1 for line in lines) * metrics["line"]
            height += self._job_aid_note_height(section.note_html, metrics)
        return height

    @api.model
    def _job_aid_lines(self, aid):
        """{recto, verso, total} printed line counts of a job aid (one per
        heading, per item — two when it wraps — and per note row)."""
        chars = dict(JOB_AID_SIZE_CLASSES)[self._job_aid_size_class(aid)]["chars"]
        counts = {}
        for face in ("recto", "verso"):
            total = 0
            for section in aid._face_sections(face):
                total += 1
                total += sum(max(1, math.ceil(len(line.text or "") / chars)) for line in section.line_ids)
                total += self._job_aid_note_lines(section.note_html, chars)
            counts[face] = total
        counts["total"] = counts["recto"] + counts["verso"]
        return counts

    @api.model
    def _job_aid_size_class(self, aid):
        """"l", "m", "s" or "xs" — the largest typography class in which both
        faces of the card fit their page (see JOB_AID_SIZE_CLASSES); "xs"
        when none does. ``cbet_job_aid_size_class`` in the context forces one."""
        forced = self.env.context.get("cbet_job_aid_size_class")
        if forced in dict(JOB_AID_SIZE_CLASSES):
            return forced
        for size_class, _metrics in JOB_AID_SIZE_CLASSES:
            if all(self._job_aid_face_height(aid, face, size_class) <= JOB_AID_PAGE_MM
                   for face in ("recto", "verso")):
                return size_class
        return JOB_AID_SIZE_CLASSES[-1][0]

    # ------------------------------------------------------------ values
    @api.model
    def _duration_label(self, hours):
        """0.75 → "~45 min" (the fiche quotes planned durations in minutes)."""
        if not hours:
            return ""
        return self.env._("~%s min", int(round(hours * 60)))

    @api.model
    def _selection_label(self, record, fname):
        value = record[fname]
        if not value:
            return ""
        return dict(record._fields[fname]._description_selection(record.env)).get(value, "")

    @api.model
    def _rows(self, rows):
        """[(label, value)] → the rows when any value is set, else False (so
        the template prints the N/A marker instead of an empty table)."""
        rows = [(label, value or "") for label, value in rows]
        return rows if any(value for _label, value in rows) else False

    @api.model
    def _protocol_rows(self, comp):
        _ = self.env._
        return self._rows([
            (_("Method"), comp.protocol_method),
            (_("Place"), comp.protocol_place),
            (_("Planned duration"), self._duration_label(comp.protocol_duration)),
            (_("Starting conditions"), comp.protocol_start_conditions),
            (_("Allowed support during the assessment"), comp.protocol_support),
            (_("Required verbalization"), comp.protocol_verbalization),
        ])

    @api.model
    def _evaluator_rows(self, comp):
        _ = self.env._
        return self._rows([
            (_("Minimum qualification"), comp.protocol_min_evaluator_qualification),
            (_("Independence"), comp.evaluator_independence),
        ])

    @api.model
    def _validity_rows(self, comp):
        _ = self.env._
        months = _("%s months", comp.validity_months) if comp.validity_months else ""
        return self._rows([
            (_("Certification validity"), months),
            (_("Maintenance condition"), comp.maintenance_condition),
            (_("Recertification modality"), comp.recert_modality),
            (_("Early recertification trigger"), comp.recert_early_trigger),
        ])

    @api.model
    def _meta_rows(self, comp):
        _ = self.env._
        return self._rows([
            (_("Field frequency"), comp.field_frequency),
            (_("Perceived difficulty"), self._selection_label(comp, "difficulty")),
            (_("Estimated learning time"), comp.learning_time),
            (_("Common pitfalls"), comp.common_pitfalls),
        ])

    @api.model
    def _documents_rows(self, comp):
        """§7 — which operational documents exist for the competency."""
        _ = self.env._
        def flag(ok, count=0):
            if not ok:
                return "—"
            return "✔ (%s)" % count if count > 1 else "✔"
        return [
            (_("Procedure"), flag(comp.has_procedure)),
            (_("Job aid"), flag(comp.has_job_aid, comp.job_aid_count)),
            (_("Demonstration notes"), flag(comp.has_demo_notes)),
        ]

    @api.model
    def _pass_rule(self, comp):
        """The global pass/fail sentence, quoting the competency's threshold
        (the engine counts the threshold over ALL applicable criteria)."""
        threshold = comp.pass_threshold or 0.0
        threshold = int(threshold) if threshold == int(threshold) else threshold
        return self.env._(
            "Pass/fail rule: the competency is passed when every security (🔒) and "
            "every critical (⚠️) criterion is passed, and at least %(threshold)s %% "
            "of all applicable criteria are passed.",
            threshold=threshold,
        )


class CbetFicheReport(models.AbstractModel):
    _name = "report.hr_skills_cbet.report_cbet_fiche"
    _inherit = "cbet.document.report"
    _description = "CBET competency sheet report"

    @api.model
    def _get_report_values(self, docids, data=None):
        return self._report_values("cbet.competency", docids)


class CbetProcedureReport(models.AbstractModel):
    _name = "report.hr_skills_cbet.report_cbet_procedure"
    _inherit = "cbet.document.report"
    _description = "CBET procedure report"

    @api.model
    def _get_report_values(self, docids, data=None):
        return self._report_values("cbet.competency", docids)


class CbetDemoNotesReport(models.AbstractModel):
    _name = "report.hr_skills_cbet.report_cbet_demo_notes"
    _inherit = "cbet.document.report"
    _description = "CBET trainer demonstration notes report"

    @api.model
    def _get_report_values(self, docids, data=None):
        values = self._report_values("cbet.competency", docids)
        values["log_rows"] = range(8)
        return values


class CbetJobAidReport(models.AbstractModel):
    _name = "report.hr_skills_cbet.report_cbet_job_aid"
    _inherit = "cbet.document.report"
    _description = "CBET field job aid report"

    @api.model
    def _get_report_values(self, docids, data=None):
        return self._report_values("cbet.job.aid", docids)
