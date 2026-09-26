# -*- coding: utf-8 -*-
"""Export records back to the family repository's CSV files (UC-11).

Every writer returns the CSV text; :meth:`export_all` writes the files under the
configured repository path and nowhere else, and :meth:`export_texts` hands the same
texts to an RPC client ("pull from home": the household machine writes, commits and
pushes; no key ever lives on the server). The exporter never runs ``git``.
"""
import csv
import io
import os

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .day import iso_week_label


def _csv(header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        # 0 is a value; None and False are blanks (0 == False in Python, hence identity checks)
        writer.writerow(["" if (v is None or v is False) else v for v in row])
    return buf.getvalue()


def _newline_of(path):
    """The line terminator used by an existing file ('\r\n' or '\n'); '\n' when absent."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4096)
    except OSError:
        return "\n"
    return "\r\n" if b"\r\n" in head else "\n"


def _date(d):
    return fields.Date.to_string(d) if d else ""


class RepositoryExporter(models.AbstractModel):
    _name = "homeschool.exporter"
    _description = "Family repository exporter"

    FILES = {
        "tracking/hours.csv": "export_hours",
        "tracking/traces.csv": "export_traces",
        "tracking/indicateurs.csv": "export_indicator_values",
        "tracking/indicateurs-definitions.csv": "export_indicator_definitions",
        "tracking/coverage.csv": "export_coverage",
        "plan/curriculum/pda-items.csv": "export_pda_items",
        "plan/curriculum/items-internes.csv": "export_internal_items",
        "plan/curriculum/projets.csv": "export_projects",
    }

    # ------------------------------------------------------------------
    # tracking/
    # ------------------------------------------------------------------
    @api.model
    def _block_key(self, block):
        """Inverse of the importer's block mapping: kind + subject → 'bloc-fle'."""
        code = (block.subject_id.code or "").lower()
        if block.kind == "bloc":
            return "bloc-%s" % code if code else "bloc"
        if block.kind == "bonus":
            return "bonus-%s" % code if code else "bonus"
        return {"reading": "lecture", "projects": "projets", "ressource": "ressource"}.get(block.kind, block.kind)

    @api.model
    def export_hours(self, student):
        header = ["date", "block", "activity", "matieres", "minutes_total", "minutes_adult_present", "notes"]
        rows = []
        days = self.env["homeschool.day"].search([("student_id", "=", student.id)], order="date")
        for day in days:
            recorded = day.block_ids.filtered(lambda b: b.actuals_recorded or b.adult_recorded)
            if day.is_off and not recorded:
                rows.append([_date(day.date), "journee", day.off_reason or "", "", 0, 0, (day.note or "").replace("\n", " ")])
                continue
            for block in recorded.sorted(lambda b: (b.sequence, b.id)):
                rows.append([
                    _date(day.date), block.csv_key or self._block_key(block), block.name,
                    block.subject_codes or block.subject_id.code or "",
                    block.minutes_total if block.actuals_recorded else "",
                    block.minutes_adult_present if block.adult_recorded else "",
                    (block.note or "").replace("\n", " "),
                ])
        return _csv(header, rows)

    @api.model
    def export_traces(self, student):
        header = ["trace_id", "date", "title", "matieres", "pda_ids", "artifact_path", "diffusion", "notes"]
        rows = []
        traces = self.env["homeschool.trace"].search([("student_id", "=", student.id)], order="date, code")
        for t in traces:
            codes = [c.strip() for c in (t.item_codes or "").split(";") if c.strip()]
            if set(codes) != set(t.item_ids.mapped("code")):
                codes = t.item_ids.sorted("code").mapped("code")
            subjects = [c.strip() for c in (t.subject_codes or "").split(";") if c.strip()]
            if set(subjects) != set(t.subject_ids.mapped("code")):
                subjects = t.subject_ids.mapped("code")
            rows.append([
                t.code, _date(t.date), t.name, ";".join(subjects),
                ";".join(codes), t.artifact_path or "",
                t.diffusion.upper(), (t.note or "").replace("\n", " "),
            ])
        return _csv(header, rows)

    @api.model
    def export_indicator_values(self, student):
        header = ["date", "id", "valeur", "notes"]
        values = self.env["homeschool.indicator.value"].search(
            ["|", ("student_id", "=", student.id), ("student_id", "=", False)], order="date, code")
        rows = [[_date(v.date), v.code, ("%g" % v.value), v.note or ""] for v in values]
        return _csv(header, rows)

    @api.model
    def export_indicator_definitions(self, student=None):
        header = ["id", "porte", "libelle", "unite", "cadence", "sens", "seuil", "source", "notes"]
        period = {"daily": "quotidien", "weekly": "hebdo", "periodic": "periodique"}
        direction = {"up": "hausse", "down": "baisse"}
        rows = []
        for i in self.env["homeschool.indicator"].search([], order="csv_sequence, code"):
            rows.append([i.code, i.porte or "", i.name, i.unit or "", i.cadence_raw or period.get(i.period, i.period),
                         i.sens_raw or direction.get(i.direction, ""), i.threshold or "", i.source or "", i.note or ""])
        return _csv(header, rows)

    @api.model
    def export_coverage(self, student=None):
        header = ["pda_id", "status", "evidence_refs", "date_updated", "notes"]
        rows = []
        items = self.env["homeschool.item"].search([("kind", "=", "pda")], order="csv_sequence, subject_id, code")
        for it in items:
            rows.append([
                it.code, it.coverage_status, ";".join(it.trace_ids.sorted("code").mapped("code")),
                _date(it.coverage_date), it.coverage_note or "",
            ])
        return _csv(header, rows)

    # ------------------------------------------------------------------
    # plan/curriculum/
    # ------------------------------------------------------------------
    @api.model
    def export_pda_items(self, student=None):
        header = ["pda_id", "matiere", "cycle", "annee", "competence", "section", "libelle", "m1", "m2", "m3", "m4", "m5", "m6",
                  "statut_3e", "noyau", "parent_id", "source_ref", "page", "annee_cible", "priorite", "notes", "projets"]
        rows = []
        for it in self.env["homeschool.item"].search([("kind", "=", "pda")], order="csv_sequence, subject_id, code"):
            rows.append([
                it.code, (it.subject_id.csv_keys or it.subject_id.code).split(",")[0], it.cycle or "", it.year_level or "",
                it.competence or "", it.section or "", it.name, it.m1 or "", it.m2 or "", it.m3 or "", it.m4 or "", it.m5 or "", it.m6 or "",
                it.statut_3e or "", it.noyau_raw if it.noyau_raw is not False else ("1" if it.noyau else ""), (it.parent_id.code if it.parent_id.kind != "section" else "") or "", it.source_ref or "", it.page or "",
                it.annee_cible or "", it.priorite or "", it.note or "", it.project_codes or ";".join(it.project_ids.mapped("code")),
            ])
        return _csv(header, rows)

    @api.model
    def export_internal_items(self, student=None):
        header = ["item_id", "domaine", "exposition", "projection", "libelle", "section", "m1", "m2", "m3", "m4", "m5", "m6", "statut_3e", "source_ref", "page", "notes"]
        rows = []
        for it in self.env["homeschool.item"].search([("kind", "=", "internal")], order="csv_sequence, code"):
            rows.append([
                it.code, it.domaine or "", it.exposition or "", it.projection or "", it.name, it.section or "",
                it.m1 or "", it.m2 or "", it.m3 or "", it.m4 or "", it.m5 or "", it.m6 or "", it.statut_3e or "",
                it.source_ref or "", it.page or "", it.note or "",
            ])
        return _csv(header, rows)

    @api.model
    def export_projects(self, student=None):
        header = ["projet_id", "titre", "type", "saison", "description", "porte"]
        rows = []
        for p in self.env["homeschool.project"].search([], order="csv_sequence, code"):
            kind = {"project": "projet", "mini_project": "mini-projet", "outing": "sortie", "transversal": "transversal"}[p.kind]
            rows.append([p.code, p.name, kind, p.season or "", p.description or "", p.carries or ""])
        return _csv(header, rows)

    # ------------------------------------------------------------------
    # writing files
    # ------------------------------------------------------------------
    @api.model
    def _repo_path(self, repo_path=None):
        path = repo_path or self.env["ir.config_parameter"].sudo().get_param("homeschool.repo_path")
        if not path:
            raise UserError(self.env._("No repository path configured (homeschool.repo_path)."))
        return os.path.realpath(path)

    @api.model
    def export_all(self, student, repo_path=None, files=None):
        """Write every CSV under the repository path. Returns the list of files written.
        Refuses any target outside the repository path; never runs git."""
        root = self._repo_path(repo_path)
        written = []
        for rel, method in self.FILES.items():
            if files and rel not in files:
                continue
            target = os.path.realpath(os.path.join(root, rel))
            if not target.startswith(root + os.sep):
                raise UserError(self.env._("Refusing to write outside the repository: %s", target))
            text = getattr(self, method)(student)
            newline = _newline_of(target)
            if newline != "\n":
                text = text.replace("\n", newline)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            written.append(rel)
        return written

    @api.model
    def export_texts(self, student_id, files=None, newline="\n"):
        """RPC entry point for the pull-from-home nightly export: ``{relative_path: csv_text}``
        for every file of :attr:`FILES` (or the ``files`` subset), for the student with id
        ``student_id``. Nothing is written on the server; the caller writes the texts into
        its own clone of the repository. ``newline`` is applied here so the client can
        write the text verbatim (``open(..., newline="")``). Managers only."""
        if not self.env.user.has_group("homeschool.group_homeschool_manager"):
            raise AccessError(self.env._("Only a homeschool manager may export the records."))
        student = self.env["homeschool.student"].browse(student_id).exists()
        if not student:
            raise UserError(self.env._("No student with id %s.", student_id))
        selected = list(files) if files else list(self.FILES)
        unknown = [rel for rel in selected if rel not in self.FILES]
        if unknown:
            raise UserError(self.env._("Unknown export file(s): %s", ", ".join(unknown)))
        texts = {}
        for rel in selected:
            text = getattr(self, self.FILES[rel])(student)
            if newline != "\n":
                text = text.replace("\n", newline)
            texts[rel] = text
        return texts

    @api.model
    def cron_export(self):
        """Nightly export for every active student, when a repository path is configured."""
        path = self.env["ir.config_parameter"].sudo().get_param("homeschool.repo_path")
        if not path:
            return
        for student in self.env["homeschool.student"].search([]):
            self.export_all(student, path)
