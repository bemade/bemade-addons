# -*- coding: utf-8 -*-
"""Export records back to the family repository's CSV files (UC-11).

Every writer returns the CSV text; :meth:`export_all` writes the files under the
configured repository path and nowhere else, and :meth:`export_texts` hands the same
texts to an RPC client ("pull from home": the household machine writes, commits and
pushes; no key ever lives on the server). The exporter never runs ``git``.
"""
import csv
import io
import logging
import os
from datetime import timedelta

from babel.dates import format_date as babel_format_date

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


def _lines(text):
    """The non-empty lines of a text, stripped."""
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


JOURNAL_WEEK_PREFIX = "tracking/journal/"


_logger = logging.getLogger(__name__)


class RepositoryExporter(models.AbstractModel):
    """One repository per family (company). Family-owned rows (hours, traces, indicators,
    projects) are filtered by the student's company; the curriculum files are shared and
    identical for every family. The file layout is the one-student layout of the household
    repository — it must not change."""
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
    def _hours_rows(self, day):
        """The ``hours.csv`` rows of one day: the ``journee`` marker first when the day is
        off, then every block with recorded minutes in sequence. Also what the journal API's
        ``status`` counts."""
        rows = []
        recorded = day.block_ids.filtered(lambda b: b.actuals_recorded or b.adult_recorded)
        if day.is_off:
            # the marker row always comes first; a bonus recorded on a day off follows it
            rows.append([_date(day.date), "journee", day.off_reason or "", "", 0, 0, (day.note or "").replace("\n", " ")])
        for block in recorded.sorted(lambda b: (b.sequence, b.id)):
            rows.append([
                _date(day.date), block.csv_key or self._block_key(block), block.name,
                block.subject_codes or block.subject_id.code or "",
                block.minutes_total if block.actuals_recorded else "",
                block.minutes_adult_present if block.adult_recorded else "",
                self._block_notes(block),
            ])
        return rows

    @api.model
    def _block_notes(self, block):
        """The ``notes`` cell of a block: its note, then its own journal folded in
        (``✓ what worked``, ``✗ what went badly``), ``·``-separated, newlines flattened.
        A block with only a note exports as it always did."""
        parts = [block.note or "", "✓ " + block.went_well if block.went_well else "", "✗ " + block.went_badly if block.went_badly else ""]
        return " · ".join(p.replace("\n", " ") for p in parts if p)

    @api.model
    def export_hours(self, student):
        header = ["date", "block", "activity", "matieres", "minutes_total", "minutes_adult_present", "notes"]
        rows = []
        days = self.env["homeschool.day"].search([("student_id", "=", student.id)], order="date")
        for day in days:
            rows += self._hours_rows(day)
        return _csv(header, rows)

    @api.model
    def export_traces(self, student):
        header = ["trace_id", "date", "title", "matieres", "pda_ids", "artifact_path", "diffusion", "notes"]
        rows = []
        # Pending (non-validated) submissions never reach the family repository: only what a
        # parent validated is part of the auditable snapshot.
        traces = self.env["homeschool.trace"].search(
            [("student_id", "=", student.id), ("validated", "=", True)], order="date, code")
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
            ["|", ("student_id", "=", student.id), "&", ("student_id", "=", False), ("company_id", "=", student.company_id.id)],
            order="date, code")
        rows = [[_date(v.date), v.code, ("%g" % v.value), v.note or ""] for v in values]
        return _csv(header, rows)

    @api.model
    def export_indicator_definitions(self, student=None):
        header = ["id", "porte", "libelle", "unite", "cadence", "sens", "seuil", "source", "notes"]
        period = {"daily": "quotidien", "weekly": "hebdo", "periodic": "periodique"}
        direction = {"up": "hausse", "down": "baisse"}
        rows = []
        domain = [("company_id", "=", student.company_id.id)] if student else []
        for i in self.env["homeschool.indicator"].search(domain, order="csv_sequence, code"):
            rows.append([i.code, i.porte or "", i.name, i.unit or "", i.cadence_raw or period.get(i.period, i.period),
                         i.sens_raw or direction.get(i.direction, ""), i.threshold or "", i.source or "", i.note or ""])
        return _csv(header, rows)

    @api.model
    def export_coverage(self, student=None):
        """The family's coverage of every PDA item: its ``homeschool.item.coverage`` rows
        (an item without a row is not started, with no evidence and no note)."""
        header = ["pda_id", "status", "evidence_refs", "date_updated", "notes"]
        rows = []
        company = student.company_id if student else self.env.company
        items = self.env["homeschool.item"].search([("kind", "=", "pda")], order="csv_sequence, subject_id, code")
        coverage = {c.item_id.id: c for c in items._coverage_for(company)}
        for it in items:
            c = coverage.get(it.id)
            rows.append([
                it.code, c.status if c else "not_started", (c.evidence_refs or "") if c else "",
                _date(c.date) if c else "", (c.note or "") if c else "",
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
            projects = it.project_ids
            if student:
                projects = projects.filtered(lambda p: p.company_id == student.company_id)
            rows.append([
                it.code, (it.subject_id.csv_keys or it.subject_id.code).split(",")[0], it.cycle or "", it.year_level or "",
                it.competence or "", it.section or "", it.name, it.m1 or "", it.m2 or "", it.m3 or "", it.m4 or "", it.m5 or "", it.m6 or "",
                it.statut_3e or "", it.noyau_raw if it.noyau_raw is not False else ("1" if it.noyau else ""), (it.parent_id.code if it.parent_id.kind != "section" else "") or "", it.source_ref or "", it.page or "",
                it.annee_cible or "", it.priorite or "", it.note or "", it.project_codes or ";".join(projects.mapped("code")),
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
        domain = [("company_id", "=", student.company_id.id)] if student else []
        for p in self.env["homeschool.project"].search(domain, order="csv_sequence, code"):
            kind = {"project": "projet", "mini_project": "mini-projet", "outing": "sortie", "transversal": "transversal"}[p.kind]
            rows.append([p.code, p.name, kind, p.season or "", p.description or "", p.carries or ""])
        return _csv(header, rows)

    # ------------------------------------------------------------------
    # tracking/journal/<ISO>/<ISO>.md — the week file, rendered (UC-19)
    # ------------------------------------------------------------------
    @api.model
    def _week_number(self, student, monday, first_day):
        """« Semaine N »: calendar weeks counted from the Monday of the week holding the
        start of the student's school year (the latest ``homeschool.year`` started by the
        week's Sunday); without one, from the week of the first day of his records."""
        years = student.year_ids.filtered(lambda y: y.date_start <= monday + timedelta(days=6)).sorted("date_start")
        start = years[-1].date_start if years else first_day
        start_monday = start - timedelta(days=start.weekday())
        return (monday - start_monday).days // 7 + 1

    @api.model
    def _journal_block_line(self, block):
        """``- Blocs : `bloc-math` P1 Math · 50/45 · done — note · ✓ … · ✗ …`` — the hours
        key, the name, total/adult minutes (``–`` when not recorded), the status, the
        ``hours.csv`` notes cell."""
        total = str(block.minutes_total) if block.actuals_recorded else "–"
        adult = str(block.minutes_adult_present) if block.adult_recorded else "–"
        line = "- Blocs : `%s` %s · %s/%s · %s" % (block.csv_key or self._block_key(block), block.name, total, adult, block.status)
        notes = self._block_notes(block)
        return line + (" — " + notes if notes else "")

    @api.model
    def _render_journal_week(self, student, iso_week, days, first_day):
        monday = days[0].date - timedelta(days=days[0].date.weekday())
        sunday = monday + timedelta(days=6)
        fr = lambda d: babel_format_date(d, "EEE d MMM", locale="fr_CA")
        lines = ["# Semaine %d · %s (%s → %s)" % (self._week_number(student, monday, first_day), iso_week, fr(monday), fr(sunday)), ""]
        review = self.env["homeschool.review"].search(
            [("student_id", "=", student.id), ("kind", "=", "weekly"), ("iso_week", "=", iso_week)], order="date desc", limit=1)
        if review:
            lines += ["## Revue de la semaine", ""]
            for label, value in (("Dose tenue ?", review.answer_dose), ("Plafond visible respecté ?", review.answer_cap),
                                 ("Semaine notée telle quelle ?", review.answer_recorded),
                                 ("Ajustement pour la semaine prochaine", review.adjustment), ("Notes", review.notes)):
                if value:
                    lines.append("- **%s :** %s" % (label, " ".join(_lines(value))))
            lines.append("")
        lines += ["## Jours", ""]
        for day in days:
            heading = "### %s" % _date(day.date)
            if day.is_off:
                heading += " — pas d'école" + (" (%s)" % day.off_reason if day.off_reason else "")
            lines.append(heading)
            recorded = day.block_ids.filtered(lambda b: b.actuals_recorded or b.adult_recorded)
            for block in recorded.sorted(lambda b: (b.sequence, b.id)):
                lines.append(self._journal_block_line(block))
            entry = day.journal_ids[:1]
            if entry:
                lines += ["- Ce qui a marché : " + l for l in _lines(entry.went_well)]
                lines += ["- Ce qui a mal été : " + l for l in _lines(entry.went_badly)]
                lines += [l if l.startswith("- ") else "- " + l for l in _lines(entry.notes)]
                lines += ["- Indicateurs : " + l for l in _lines(entry.indicator_notes)]
                if entry.corrections:
                    lines.append("- Corrections :")
                    lines += ["  " + l for l in _lines(entry.corrections)]
            lines.append("")
        return "\n".join(lines).rstrip("\n") + "\n"

    @api.model
    def export_journal_weeks(self, student):
        """``{"tracking/journal/<ISO>/<ISO>.md": text}`` for every ISO week holding at least
        one day of the student that has blocks, a journal entry or is a day off — the
        household's week file, rendered from the records (French headings, importable by
        ``import_journal``: the ``- Blocs :`` lines and the corrections are ignored on the
        way back, the entry's bullets are re-read as written)."""
        days = self.env["homeschool.day"].search([("student_id", "=", student.id)], order="date, id")
        days = days.filtered(lambda d: d.block_ids or d.journal_ids or d.is_off)
        if not days:
            return {}
        first_day = days[0].date
        texts = {}
        for iso_week, week_days in days.grouped("iso_week").items():
            texts["%s%s/%s.md" % (JOURNAL_WEEK_PREFIX, iso_week, iso_week)] = self._render_journal_week(
                student, iso_week, week_days.sorted("date"), first_day)
        return dict(sorted(texts.items()))

    # ------------------------------------------------------------------
    # writing files
    # ------------------------------------------------------------------
    @api.model
    def _configured_repo_path(self, company=None):
        """The repository path of ``company``: ``homeschool.repo_path.<company_id>``, falling back
        to the global ``homeschool.repo_path``. Empty string when neither is set."""
        Param = self.env["ir.config_parameter"].sudo()
        path = Param.get_param("homeschool.repo_path.%d" % company.id) if company else ""
        return path or Param.get_param("homeschool.repo_path") or ""

    @api.model
    def _repo_path(self, repo_path=None, company=None):
        path = repo_path or self._configured_repo_path(company)
        if not path:
            raise UserError(self.env._("No repository path configured (homeschool.repo_path)."))
        return os.path.realpath(path)

    @api.model
    def export_all(self, student, repo_path=None, files=None):
        """Write every CSV under the repository path of the student's family. Returns the list
        of files written. Refuses any target outside the repository path; never runs git."""
        root = self._repo_path(repo_path, student.company_id)
        written = []
        for rel, text in self._texts(student, files).items():
            target = os.path.realpath(os.path.join(root, rel))
            if not target.startswith(root + os.sep):
                raise UserError(self.env._("Refusing to write outside the repository: %s", target))
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
        texts = self._texts(student, files)
        if newline != "\n":
            texts = {rel: text.replace("\n", newline) for rel, text in texts.items()}
        return texts

    @api.model
    def _texts(self, student, files=None):
        """``{relative_path: text}`` of :attr:`FILES` followed by the rendered journal week
        files (dynamic paths), or the ``files`` subset — an unknown name is a ``UserError``."""
        weeks = {}
        if not files or any(rel.startswith(JOURNAL_WEEK_PREFIX) for rel in files):
            weeks = self.export_journal_weeks(student)
        selected = list(files) if files else list(self.FILES) + list(weeks)
        unknown = [rel for rel in selected if rel not in self.FILES and rel not in weeks]
        if unknown:
            raise UserError(self.env._("Unknown export file(s): %s", ", ".join(unknown)))
        return {rel: (weeks[rel] if rel in weeks else getattr(self, self.FILES[rel])(student)) for rel in selected}

    @api.model
    def cron_export(self):
        """Nightly export, family by family: every active student is exported under his
        company's repository path; companies without any path (own or global) are skipped."""
        students = self.env["homeschool.student"].sudo().search([])
        for company, company_students in students.grouped("company_id").items():
            path = self._configured_repo_path(company)
            if not path:
                continue
            if len(company_students) > 1:
                _logger.warning("homeschool: %d students in %s share the repository %s; "
                                "the export keeps the one-student file layout and the last student wins",
                                len(company_students), company.name, path)
            for student in company_students:
                self.with_company(company).export_all(student, path)
