import base64

from odoo import api, models

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
