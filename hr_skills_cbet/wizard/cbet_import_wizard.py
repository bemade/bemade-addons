import base64
import io
import posixpath
import re
import zipfile

from odoo import _, fields, models
from odoo.exceptions import UserError

# FICHE_ADO-01.md, EVALUATION_ADO-01_EN.md, JOB_AID_UNI-02_RO.md (the optional
# third group is a job-aid variant; it is ignored for the other kinds).
FILE_RE = re.compile(
    r"(?:^|/)(FICHE|EVALUATION|PROCEDURE|JOB_AID|NOTES_DEMO)_([A-Z]{2,4}-\d{1,3})"
    r"(?:_(?!EN\.md$)([A-Z]+))?(_EN)?\.md$")
DOC_KINDS = ("FICHE", "EVALUATION", "PROCEDURE", "JOB_AID", "NOTES_DEMO")


class CbetImportWizard(models.TransientModel):
    """UC-CAT-10 — in-product markdown import, with a dry-run (validate-only) mode.

    Two sources: paste a single competency's FICHE + EVALUATION markdown, or
    upload a .zip of the content vault to process many — fiches, grids,
    procedures, job aids (incl. variants) and demo notes, with their English
    editions and the images the procedures reference. Imports create draft
    competencies (idempotent by code); prerequisites link in a second pass.
    """

    _name = "cbet.import.wizard"
    _description = "CBET Markdown Import"

    import_mode = fields.Selection(
        [("single", "Single competency (paste)"), ("archive", "Content vault (.zip)")],
        default="single", required=True,
    )
    fiche_text = fields.Text("FICHE markdown")
    evaluation_text = fields.Text("EVALUATION markdown")
    fiche_en_text = fields.Text(
        "FICHE markdown (English)",
        help="Optional English edition of the fiche. Supplied, it becomes the "
             "source-language text and the French is kept as its translation.")
    evaluation_en_text = fields.Text(
        "EVALUATION markdown (English)",
        help="Optional English edition of the evaluation grid. It is used only "
             "when it has the same number of criteria and questions as the "
             "French, so a mismatched translation cannot pair the wrong rows.")
    archive_file = fields.Binary("Vault archive (.zip)")
    archive_filename = fields.Char()

    state = fields.Selection([("input", "Input"), ("done", "Done")], default="input")
    was_dry_run = fields.Boolean(readonly=True)
    result_log = fields.Text(readonly=True)
    imported_count = fields.Integer(readonly=True)

    # ------------------------------------------------------------------ sources
    def _collect_pairs(self):
        """Return (entries, skipped), entries being [(label, docs)] where docs is
        the per-competency document dict: FICHE, EVALUATION, PROCEDURE,
        NOTES_DEMO (each with an optional ``_EN`` twin), JOB_AID as a list of
        ``{variant, md, md_en}`` and ``image_loader`` for the procedure images.

        The English editions are picked up as the source-language text rather
        than ignored; any may be absent, in which case that part keeps the
        French in both languages.
        """
        self.ensure_one()
        if self.import_mode == "single":
            if not (self.fiche_text and self.evaluation_text):
                raise UserError(_("Paste both the FICHE and EVALUATION markdown."))
            return [("(pasted)", {
                "FICHE": self.fiche_text, "EVALUATION": self.evaluation_text,
                "FICHE_EN": self.fiche_en_text or None,
                "EVALUATION_EN": self.evaluation_en_text or None,
            })], []

        if not self.archive_file:
            raise UserError(_("Upload a .zip archive of the content vault."))
        try:
            zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(self.archive_file)))
        except (zipfile.BadZipFile, ValueError):
            raise UserError(_("The uploaded file is not a valid .zip archive."))

        names = set(zf.namelist())
        found = {}
        for name in zf.namelist():
            m = FILE_RE.search(name)
            if not m:
                continue
            kind, code, variant, en = m.groups()
            files = found.setdefault(code, {"JOB_AID": {}, "_dirs": set()})
            files["_dirs"].add(posixpath.dirname(name))
            if kind == "JOB_AID":
                files["JOB_AID"].setdefault(variant or None, {})["md_en" if en else "md"] = name
            else:
                files[kind + ("_EN" if en else "")] = name

        def read(name):
            return zf.read(name).decode("utf-8") if name else None

        def loader_for(dirs):
            def load(rel):
                for d in dirs:
                    path = posixpath.normpath(posixpath.join(d, rel)) if d else rel
                    if path in names:
                        return zf.read(path)
                return None
            return load

        entries, skipped = [], []
        for code, files in sorted(found.items()):
            if "FICHE" not in files or "EVALUATION" not in files:
                skipped.append((code, "missing FICHE or EVALUATION"))
                continue
            docs = {k: read(files.get(k)) for k in
                    ("FICHE", "EVALUATION", "FICHE_EN", "EVALUATION_EN",
                     "PROCEDURE", "PROCEDURE_EN", "NOTES_DEMO", "NOTES_DEMO_EN")}
            docs["JOB_AID"] = [
                {"variant": variant, "md": read(spec.get("md")), "md_en": read(spec.get("md_en"))}
                for variant, spec in sorted(files["JOB_AID"].items(), key=lambda kv: kv[0] or "")
                if spec.get("md")
            ]
            docs["image_loader"] = loader_for(sorted(files["_dirs"]))
            entries.append((code, docs))
        return entries, skipped

    # ------------------------------------------------------------------ actions
    def action_dry_run(self):
        return self._finish(*self._dry_run(*self._collect_pairs()), dry=True)

    def action_import(self):
        entries, skipped = self._collect_pairs()
        # Single paste: surface a parse error as a clear popup. Archive import:
        # stay resilient — bad pairs are reported in the log, others still load.
        return self._finish(
            *self._do_import(entries, skipped, raise_errors=self.import_mode == "single"),
            dry=False)

    def _finish(self, count, log, dry):
        self.write({"state": "done", "result_log": log,
                    "imported_count": count, "was_dry_run": dry})
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new"}

    # ------------------------------------------------------------------ engines
    @staticmethod
    def _coverage_lines(rows, total, prefix="  "):
        """The per-document-kind coverage block shared by both reports.
        *rows* is [(has_procedure, has_procedure_en, has_notes, has_notes_en,
        n_job_aids, n_job_aids_en)]."""
        proc = sum(1 for r in rows if r[0])
        proc_en = sum(1 for r in rows if r[1])
        notes = sum(1 for r in rows if r[2])
        notes_en = sum(1 for r in rows if r[3])
        aids = sum(r[4] for r in rows)
        aids_en = sum(r[5] for r in rows)
        with_aid = sum(1 for r in rows if r[4])
        return [
            prefix + "documents: procedure %s of %s (English %s)   job aids %s on %s "
                     "competencies (English %s)   demo notes %s of %s (English %s)"
            % (proc, total, proc_en, aids, with_aid, aids_en, notes, total, notes_en),
        ]

    def _do_import(self, entries, skipped, raise_errors=False):
        Comp = self.env["cbet.competency"]
        ok, errors, prereq_by_code, warnings = [], [], {}, []
        translated = grids = 0
        coverage = []
        for label, docs in entries:
            try:
                comp, prereqs = Comp._import_markdown(
                    docs.get("FICHE"), docs.get("EVALUATION"), docs.get("FICHE_EN"),
                    docs.get("EVALUATION_EN"), docs=docs, warnings=warnings)
                prereq_by_code[comp.code] = prereqs
                ok.append((comp.code, len(comp.criterion_ids), len(comp.question_ids)))
                translated += bool(docs.get("FICHE_EN"))
                grids += bool(docs.get("EVALUATION_EN"))
                aids = docs.get("JOB_AID") or []
                coverage.append((comp.has_procedure, bool(docs.get("PROCEDURE_EN")),
                                 comp.has_demo_notes, bool(docs.get("NOTES_DEMO_EN")),
                                 len(aids), sum(1 for a in aids if a.get("md_en"))))
            except Exception as e:                       # noqa: BLE001 - report, keep going
                if raise_errors:
                    raise
                errors.append((label, str(e)[:100]))

        edges_before = self.env["cbet.prerequisite"].search_count([])
        for code, specs in prereq_by_code.items():
            Comp._link_prerequisites(code, specs)
        edges = self.env["cbet.prerequisite"].search_count([]) - edges_before

        lines = ["Imported %s competencies." % len(ok),
                 "  criteria: %s   questions: %s   prerequisite edges: +%s" % (
                     sum(c for _c, c, _q in ok), sum(q for _c, _c2, q in ok), edges)]
        lines.append("  English fiche supplied for %s of %s, English grid for "
                     "%s; the rest keep the French in both languages."
                     % (translated, len(ok), grids))
        lines += self._coverage_lines(coverage, len(ok))
        if ok:
            lines.append("  " + ", ".join(sorted(c for c, _c, _q in ok)))
        if skipped:
            lines.append("  skipped (%s): %s" % (len(skipped), ", ".join(c for c, _r in skipped)))
        if warnings:
            lines.append("  warnings (%s):" % len(warnings))
            lines += ["    %s: %s" % (c, w) for c, w in warnings]
        if errors:
            lines.append("  ERRORS (%s):" % len(errors))
            lines += ["    %s: %s" % (c, m) for c, m in errors]
        return len(ok), "\n".join(lines)

    def _dry_run(self, entries, skipped):
        Comp = self.env["cbet.competency"]
        reports = [dict(Comp._analyze_markdown(docs.get("FICHE"), docs.get("EVALUATION"), docs),
                        label=label, has_en=bool(docs.get("FICHE_EN")),
                        has_grid_en=bool(docs.get("EVALUATION_EN")))
                   for label, docs in entries]
        good = [r for r in reports if not r["error"]]
        errors = [(r.get("label") or r.get("code") or "?", r["error"])
                  for r in reports if r["error"]]

        known = {r["code"] for r in good} | set(Comp.search([]).mapped("code"))
        db_domains = set(self.env["cbet.domain"].search([]).mapped("code"))
        unresolved = [(r["code"], p["code"]) for r in good
                      for p in r["prereqs"] if p["code"] not in known]
        warnings = [(r["code"], w) for r in good for w in r["warnings"]]
        new_domains = sorted({r["domain_code"] for r in good} - db_domains)

        creates = [r for r in good if not r["exists"]]
        updates = [r for r in good if r["exists"]]
        lines = [
            "DRY RUN — nothing was changed.",
            "  competencies: %s  (create: %s, update: %s)" % (len(good), len(creates), len(updates)),
            "  criteria: %s   questions: %s (essential %s)   prerequisite edges: %s" % (
                sum(r["n_criteria"] for r in good), sum(r["n_questions"] for r in good),
                sum(r["n_essential"] for r in good), sum(len(r["prereqs"]) for r in good)),
        ]
        lines.append("  English fiche found for %s of %s, English grid for %s; "
                     "the rest would keep the French in both languages." % (
                         sum(1 for r in good if r.get("has_en")), len(good),
                         sum(1 for r in good if r.get("has_grid_en"))))
        lines += self._coverage_lines(
            [(r["has_procedure"], r["has_procedure_en"], r["has_notes"], r["has_notes_en"],
              r["n_job_aids"], r["n_job_aids_en"]) for r in good], len(good))
        if new_domains:
            lines.append("  new domains: %s" % ", ".join(new_domains))
        if skipped:
            lines.append("  skipped file-pairs (%s): %s" % (len(skipped), ", ".join(c for c, _r in skipped)))
        if unresolved:
            lines.append("  UNRESOLVED prerequisites (%s):" % len(unresolved))
            lines += ["    %s requires %s — not in this import nor the catalog" % (c, p)
                      for c, p in unresolved]
        if warnings:
            lines.append("  warnings (%s):" % len(warnings))
            lines += ["    %s: %s" % (c, w) for c, w in warnings]
        if errors:
            lines.append("  ERRORS (%s):" % len(errors))
            lines += ["    %s: %s" % (c, m) for c, m in errors]
        lines.append("")
        lines.append("  %-8s %-11s  crit  quest(ess)  prereq  sect  proc  aids  notes  action"
                     % ("code", "kind"))
        for r in sorted(good, key=lambda r: r["code"]):
            lines.append("  %-8s %-11s  %4s  %5s(%s)   %4s   %4s  %4s  %4s  %5s  %s" % (
                r["code"], r["kind"], r["n_criteria"], r["n_questions"], r["n_essential"],
                len(r["prereqs"]), r["n_sections"],
                "yes" if r["has_procedure"] else "-", r["n_job_aids"] or "-",
                "yes" if r["has_notes"] else "-",
                "update" if r["exists"] else "new"))
        return len(good), "\n".join(lines)

    def action_view_competencies(self):
        return {"type": "ir.actions.act_window", "name": _("Competencies"),
                "res_model": "cbet.competency", "view_mode": "list,form"}
