import io
import zipfile

from odoo import Command, api, fields, models
from odoo.exceptions import UserError

# (flag field, report xml id, "one per competency" or "one per job aid")
DOCUMENT_KINDS = [
    ("print_fiche", "hr_skills_cbet.action_report_cbet_fiche", "competency"),
    ("print_procedure", "hr_skills_cbet.action_report_cbet_procedure", "competency"),
    ("print_job_aid", "hr_skills_cbet.action_report_cbet_job_aid", "job_aid"),
    ("print_demo_notes", "hr_skills_cbet.action_report_cbet_demo_notes", "competency"),
]


class CbetPrintWizard(models.TransientModel):
    """UC-RPT-07 — print the training documents of one or more competencies in
    a chosen language: one PDF when a single document comes out, a zip of
    PDFs otherwise."""

    _name = "cbet.print.wizard"
    _description = "Print CBET training documents"

    competency_ids = fields.Many2many(
        "cbet.competency", string="Competencies", required=True,
    )
    lang = fields.Selection(
        selection=lambda self: self.env["res.lang"].get_installed(),
        string="Language", required=True,
    )
    print_fiche = fields.Boolean(string="Competency sheet", default=True)
    print_procedure = fields.Boolean(string="Procedure")
    print_job_aid = fields.Boolean(string="Job aid")
    print_demo_notes = fields.Boolean(string="Demonstration notes")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        comps = self.env["cbet.competency"]
        if ctx.get("active_model") == "cbet.competency":
            comps = comps.browse(ctx.get("active_ids") or [])
        elif ctx.get("active_model") == "cbet.job.aid":
            comps = self.env["cbet.job.aid"].browse(ctx.get("active_ids") or []).competency_id
        res.update({
            "competency_ids": [Command.set(comps.ids)],
            "lang": self.env.user.lang or self.env.lang or "en_US",
            "print_fiche": True,
            "print_procedure": any(comps.mapped("has_procedure")),
            "print_job_aid": any(comps.mapped("has_job_aid")),
            "print_demo_notes": any(comps.mapped("has_demo_notes")),
        })
        return res

    def _documents(self):
        """[(file name, pdf bytes)] for the selected kinds, in the chosen language."""
        self.ensure_one()
        Report = self.env["ir.actions.report"].with_context(lang=self.lang)
        comps = self.competency_ids.with_context(lang=self.lang)
        docs = []

        def render(xmlid, record):
            report = self.env.ref(xmlid)
            pdf, _type = Report._render_qweb_pdf(xmlid, record.ids)
            docs.append((Report._cbet_print_name(report, record) + ".pdf", pdf))

        for comp in comps:
            for flag, xmlid, per in DOCUMENT_KINDS:
                if not self[flag]:
                    continue
                if per == "job_aid":
                    for aid in comp.job_aid_ids:
                        render(xmlid, aid)
                elif flag == "print_procedure" and not comp.has_procedure:
                    continue
                elif flag == "print_demo_notes" and not comp.has_demo_notes:
                    continue
                else:
                    render(xmlid, comp)
        return docs

    def action_print(self):
        self.ensure_one()
        docs = self._documents()
        if not docs:
            raise UserError(self.env._(
                "Nothing to print: pick at least one document kind that exists "
                "for the selected competencies."))
        if len(docs) == 1:
            name, data = docs[0]
            mimetype = "application/pdf"
        else:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                for name, data in docs:
                    archive.writestr(name, data)
            data = buffer.getvalue()
            mimetype = "application/zip"
            if len(self.competency_ids) == 1:
                comp = self.competency_ids
                name = "%s_v%s_documents.zip" % (comp.code, comp.version)
            else:
                name = "cbet_documents.zip"
        # No res_model: the attachment stays private to its creator (and the
        # administrators) and outlives the transient wizard record.
        attachment = self.env["ir.attachment"].create({
            "name": name, "raw": data, "mimetype": mimetype,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%d?download=true" % attachment.id,
            "target": "self",
        }
