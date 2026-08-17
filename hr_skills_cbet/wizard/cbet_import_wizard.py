import base64
import io
import re
import zipfile

from odoo import _, fields, models
from odoo.exceptions import UserError

FILE_RE = re.compile(r"(?:^|/)(FICHE|EVALUATION)_([A-Z]{2,4}-\d{1,3})\.md$")


class CbetImportWizard(models.TransientModel):
    """UC-CAT-10 — in-product markdown import, with a dry-run (validate-only) mode.

    Two sources: paste a single competency's FICHE + EVALUATION markdown, or
    upload a .zip of the content vault to process many. Imports create draft
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
    archive_file = fields.Binary("Vault archive (.zip)")
    archive_filename = fields.Char()

    state = fields.Selection([("input", "Input"), ("done", "Done")], default="input")
    was_dry_run = fields.Boolean(readonly=True)
    result_log = fields.Text(readonly=True)
    imported_count = fields.Integer(readonly=True)

    # ------------------------------------------------------------------ sources
    def _collect_pairs(self):
        """Return (pairs, skipped): pairs = [(label, fiche_md, eval_md)],
        skipped = [(code, reason)]."""
        self.ensure_one()
        if self.import_mode == "single":
            if not (self.fiche_text and self.evaluation_text):
                raise UserError(_("Paste both the FICHE and EVALUATION markdown."))
            return [("(pasted)", self.fiche_text, self.evaluation_text)], []

        if not self.archive_file:
            raise UserError(_("Upload a .zip archive of the content vault."))
        try:
            zf = zipfile.ZipFile(io.BytesIO(base64.b64decode(self.archive_file)))
        except (zipfile.BadZipFile, ValueError):
            raise UserError(_("The uploaded file is not a valid .zip archive."))

        found = {}
        for name in zf.namelist():
            m = FILE_RE.search(name)
            if not m or name.endswith("_EN.md"):
                continue
            found.setdefault(m.group(2), {})[m.group(1)] = name

        pairs, skipped = [], []
        for code, files in sorted(found.items()):
            if "FICHE" not in files or "EVALUATION" not in files:
                skipped.append((code, "missing FICHE or EVALUATION"))
                continue
            pairs.append((code, zf.read(files["FICHE"]).decode("utf-8"),
                          zf.read(files["EVALUATION"]).decode("utf-8")))
        return pairs, skipped

    # ------------------------------------------------------------------ actions
    def action_dry_run(self):
        return self._finish(*self._dry_run(*self._collect_pairs()), dry=True)

    def action_import(self):
        pairs, skipped = self._collect_pairs()
        # Single paste: surface a parse error as a clear popup. Archive import:
        # stay resilient — bad pairs are reported in the log, others still load.
        return self._finish(
            *self._do_import(pairs, skipped, raise_errors=self.import_mode == "single"),
            dry=False)

    def _finish(self, count, log, dry):
        self.write({"state": "done", "result_log": log,
                    "imported_count": count, "was_dry_run": dry})
        return {"type": "ir.actions.act_window", "res_model": self._name,
                "res_id": self.id, "view_mode": "form", "target": "new"}

    # ------------------------------------------------------------------ engines
    def _do_import(self, pairs, skipped, raise_errors=False):
        Comp = self.env["cbet.competency"]
        ok, errors, prereq_by_code = [], [], {}
        for label, fiche, ev in pairs:
            try:
                comp, prereqs = Comp._import_markdown(fiche, ev)
                prereq_by_code[comp.code] = prereqs
                ok.append((comp.code, len(comp.criterion_ids), len(comp.question_ids)))
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
        if ok:
            lines.append("  " + ", ".join(sorted(c for c, _c, _q in ok)))
        if skipped:
            lines.append("  skipped (%s): %s" % (len(skipped), ", ".join(c for c, _r in skipped)))
        if errors:
            lines.append("  ERRORS (%s):" % len(errors))
            lines += ["    %s: %s" % (c, m) for c, m in errors]
        return len(ok), "\n".join(lines)

    def _dry_run(self, pairs, skipped):
        Comp = self.env["cbet.competency"]
        reports = [dict(Comp._analyze_markdown(f, e), label=label) for label, f, e in pairs]
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
        lines.append("  %-8s %-11s  crit  quest(ess)  prereq  action" % ("code", "kind"))
        for r in sorted(good, key=lambda r: r["code"]):
            lines.append("  %-8s %-11s  %4s  %5s(%s)   %4s   %s" % (
                r["code"], r["kind"], r["n_criteria"], r["n_questions"], r["n_essential"],
                len(r["prereqs"]), "update" if r["exists"] else "new"))
        return len(good), "\n".join(lines)

    def action_view_competencies(self):
        return {"type": "ir.actions.act_window", "name": _("Competencies"),
                "res_model": "cbet.competency", "view_mode": "list,form"}
