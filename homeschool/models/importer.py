# -*- coding: utf-8 -*-
"""Import the family repository's CSV and Markdown files into records (UC-01, 04, 05, 06, 07, 08, 09).

Everything is keyed by the stable ids of the repository (PDA ids, TR codes, indicator
codes…), stored as ``code`` and mirrored as external ids ``homeschool.<model>_<code>`` so
that re-running an import updates in place. Problems are collected in ``self.log`` and
returned, never silently dropped.
"""
import csv
import io
import os
import re

from odoo import api, fields, models

XMLID_SAFE = re.compile(r"[^A-Za-z0-9_]")


def _xmlid(prefix, code):
    return "homeschool.%s_%s" % (prefix, XMLID_SAFE.sub("_", code))


def _split(value, sep=";"):
    return [v.strip() for v in (value or "").split(sep) if v.strip()]


class RepositoryImporter(models.AbstractModel):
    _name = "homeschool.importer"
    _description = "Family repository importer"

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @api.model
    def _read_csv(self, path):
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        # comment lines starting with '#' (deps-requires.csv) are skipped
        lines = [l for l in text.splitlines() if not l.startswith("#")]
        rows = []
        for row in csv.DictReader(io.StringIO("\n".join(lines))):
            extra = row.pop(None, None)
            if extra:
                # an unquoted comma inside the last column: put the overflow back where it belongs
                last = list(row.keys())[-1]
                row[last] = ",".join([row[last] or ""] + list(extra))
            rows.append(row)
        return rows

    @api.model
    def _upsert(self, model, prefix, code, vals):
        """Create or update the record identified by ``code``; keep its external id."""
        Model = self.env[model]
        rec = Model.with_context(active_test=False).search([("code", "=", code)], limit=1)
        if rec:
            rec.write(vals)
        else:
            rec = Model.create(dict(vals, code=code))
        xmlid = _xmlid(prefix, code)
        if not self.env.ref(xmlid, raise_if_not_found=False):
            module, name = xmlid.split(".", 1)
            self.env["ir.model.data"].create({
                "module": module, "name": name, "model": model, "res_id": rec.id, "noupdate": True,
            })
        return rec

    # ------------------------------------------------------------------
    # UC-01 curriculum
    # ------------------------------------------------------------------
    @api.model
    def import_curriculum(self, repo_path):
        """pda-items.csv, items-internes.csv, covers.csv, deps-requires.csv. Returns a log (list of str)."""
        log = []
        cur = os.path.join(repo_path, "plan", "curriculum")
        Subject = self.env["homeschool.subject"]
        Item = self.env["homeschool.item"]
        Project = self.env["homeschool.project"]

        pda_path = os.path.join(cur, "pda-items.csv")
        if os.path.exists(pda_path):
            rows = self._read_csv(pda_path)
            parents = {}
            for seq, r in enumerate(rows, start=1):
                code = r["pda_id"].strip()
                if not code:
                    continue
                vals = {
                    "csv_sequence": seq,
                    "name": r.get("libelle") or code,
                    "kind": "pda",
                    "subject_id": Subject._by_csv_key(r.get("matiere")).id,
                    "cycle": r.get("cycle") or False,
                    "year_level": r.get("annee") or False,
                    "competence": r.get("competence") or False,
                    "section": r.get("section") or False,
                    "m1": r.get("m1") or False, "m2": r.get("m2") or False, "m3": r.get("m3") or False,
                    "m4": r.get("m4") or False, "m5": r.get("m5") or False, "m6": r.get("m6") or False,
                    "statut_3e": r.get("statut_3e") or False,
                    "noyau": (r.get("noyau") or "").strip().lower() in ("1", "true", "x", "oui", "yes", "noyau"),
                    "noyau_raw": (r.get("noyau") or "").strip() or False,
                    "source_ref": r.get("source_ref") or False,
                    "page": r.get("page") or False,
                    "annee_cible": r.get("annee_cible") or False,
                    "priorite": (r.get("priorite") or False) or False,
                    "note": r.get("notes") or False,
                    "project_codes": r.get("projets") or False,
                }
                if vals["priorite"] not in dict(Item._fields["priorite"].selection):
                    if vals["priorite"]:
                        log.append("pda-items.csv %s: unknown priorite %r" % (code, vals["priorite"]))
                    vals["priorite"] = False
                self._upsert("homeschool.item", "item", code, vals)
                if r.get("parent_id"):
                    parents[code] = r["parent_id"].strip()
            for code, parent_code in parents.items():
                parent = Item._by_code(parent_code)
                if parent:
                    Item._by_code(code).parent_id = parent
                else:
                    log.append("pda-items.csv %s: unknown parent %r" % (code, parent_code))
            for r in rows:
                codes = _split(r.get("projets"))
                if codes:
                    projects = Project.browse()
                    for pc in codes:
                        p = Project._by_code(pc)
                        if p:
                            projects |= p
                        else:
                            log.append("pda-items.csv %s: unknown project %r" % (r["pda_id"], pc))
                    Item._by_code(r["pda_id"].strip()).project_ids = projects
            log.append("pda-items.csv: %d rows" % len(rows))

        int_path = os.path.join(cur, "items-internes.csv")
        if os.path.exists(int_path):
            rows = self._read_csv(int_path)
            for seq, r in enumerate(rows, start=1):
                code = r["item_id"].strip()
                if not code:
                    continue
                self._upsert("homeschool.item", "item", code, {
                    "csv_sequence": seq,
                    "name": r.get("libelle") or code,
                    "kind": "internal",
                    "subject_id": Subject._by_csv_key(r.get("domaine")).id,
                    "domaine": r.get("domaine") or False,
                    "exposition": r.get("exposition") or False,
                    "projection": r.get("projection") or False,
                    "section": r.get("section") or False,
                    "m1": r.get("m1") or False, "m2": r.get("m2") or False, "m3": r.get("m3") or False,
                    "m4": r.get("m4") or False, "m5": r.get("m5") or False, "m6": r.get("m6") or False,
                    "statut_3e": r.get("statut_3e") or False,
                    "source_ref": r.get("source_ref") or False,
                    "page": r.get("page") or False,
                    "note": r.get("notes") or False,
                })
            log.append("items-internes.csv: %d rows" % len(rows))

        nodes_path = os.path.join(cur, "deps-nodes.csv")
        if os.path.exists(nodes_path):
            rows = self._read_csv(nodes_path)
            n = 0
            for r in rows:
                code = (r.get("pda_id") or "").strip()
                if not code or Item._by_code(code):
                    continue
                Item.create({
                    "code": code, "name": r.get("libelle") or code, "kind": "pda", "active": False, "in_registry": False,
                    "subject_id": Subject._by_csv_key(r.get("matiere")).id, "competence": r.get("competence") or False,
                })
                n += 1
            log.append("deps-nodes.csv: %d rows, %d nodes outside the registry created inactive" % (len(rows), n))

        cov_path = os.path.join(cur, "covers.csv")
        if os.path.exists(cov_path):
            rows = self._read_csv(cov_path)
            refs = 0
            for r in rows:
                internal = Item._resolve(r["internal_id"].strip())
                target_code = r["covers_id"].strip()
                if not internal:
                    log.append("covers.csv %s → %s: unknown internal item" % (r["internal_id"], target_code))
                    continue
                target = Item._resolve(target_code)
                if not target:
                    # a document reference (PA-1.3, a decision…), not an item: kept as text
                    for it in internal._descendants():
                        current = [c for c in (it.covers_refs or "").split(";") if c]
                        if target_code not in current:
                            it.covers_refs = ";".join(current + [target_code])
                    refs += 1
                    continue
                for it in internal._descendants():
                    it.covers_ids |= target._descendants()
                    it.covers_basis = r.get("basis") or it.covers_basis
            log.append("covers.csv: %d rows (%d document refs kept as text)" % (len(rows), refs))

        dep_path = os.path.join(cur, "deps-requires.csv")
        if os.path.exists(dep_path):
            rows = self._read_csv(dep_path)
            Dep = self.env["homeschool.item.dependency"]
            n = 0
            for r in rows:
                src = Item._resolve((r.get("from_id") or "").strip())
                dst = Item._resolve((r.get("to_id") or "").strip())
                if not src or not dst:
                    log.append("deps-requires.csv %s → %s: unknown item" % (r.get("from_id"), r.get("to_id")))
                    continue
                if not Dep.search([("from_item_id", "=", src.id), ("to_item_id", "=", dst.id)], limit=1):
                    Dep.create({"from_item_id": src.id, "to_item_id": dst.id, "basis": r.get("basis"),
                                "mode": r.get("mode"), "note": r.get("note")})
                    n += 1
            log.append("deps-requires.csv: %d rows, %d new edges" % (len(rows), n))
        return log

    # ------------------------------------------------------------------
    # UC-09 projects
    # ------------------------------------------------------------------
    @api.model
    def import_projects(self, repo_path):
        """plan/curriculum/projets.csv → homeschool.project (codes preserved)."""
        log = []
        path = os.path.join(repo_path, "plan", "curriculum", "projets.csv")
        if not os.path.exists(path):
            return log
        rows = self._read_csv(path)
        for seq, r in enumerate(rows, start=1):
            code = (r.get("projet_id") or "").strip()
            if not code:
                continue
            raw_kind = (r.get("type") or "").strip().lower()
            kind = {"projet": "project", "mini-projet": "mini_project", "mini_projet": "mini_project", "sortie": "outing", "transversal": "transversal"}.get(raw_kind, "mini_project" if raw_kind.startswith("mini") else "project")
            self._upsert("homeschool.project", "project", code, {
                "csv_sequence": seq,
                "name": r.get("titre") or code,
                "kind": kind,
                "season": r.get("saison") or False,
                "description": r.get("description") or False,
                "carries": r.get("porte") or False,
                "state": "active",
            })
        log.append("projets.csv: %d rows" % len(rows))
        return log

    # ------------------------------------------------------------------
    # UC-04 hours.csv → blocks
    # ------------------------------------------------------------------
    DEFAULT_BLOCK_ALIASES = {
        "lecture": ("reading", None),
        "projets": ("projects", None),
        "journee": ("journee", None),
        "bloc-matin": ("bloc", None),
        "block": ("bloc", None),
    }

    @api.model
    def _block_kind_and_subject(self, key, aliases):
        """'bloc-fle' → ('bloc', FLE); 'bonus-st' → ('bonus', ST); aliases first."""
        key = (key or "").strip().lower()
        Subject = self.env["homeschool.subject"]
        table = dict(self.DEFAULT_BLOCK_ALIASES)
        table.update({k.lower(): v for k, v in (aliases or {}).items()})
        if key in table:
            kind, subject_code = table[key]
            return kind, (Subject._by_csv_key(subject_code) if subject_code else Subject.browse())
        if "-" in key:
            prefix, _, suffix = key.partition("-")
            if prefix in ("bloc", "bonus"):
                return prefix, Subject._by_csv_key(suffix)
        return "bloc", Subject.browse()

    @api.model
    def import_hours(self, repo_path, student, aliases=None):
        """tracking/hours.csv → one block per row (actuals), days created as needed.
        ``aliases`` maps household-specific block keys to (kind, subject_code)."""
        log = []
        path = os.path.join(repo_path, "tracking", "hours.csv")
        if not os.path.exists(path):
            return log
        Day = self.env["homeschool.day"]
        Block = self.env["homeschool.block"]
        rows = self._read_csv(path)
        for n, r in enumerate(rows, start=1):
            d = fields.Date.to_date(r["date"].strip())
            day = Day._get_or_create(student, d)
            kind, subject = self._block_kind_and_subject(r.get("block"), aliases)
            note = r.get("notes") or False
            if kind == "journee" and not int(r.get("minutes_total") or 0):
                day.write({"is_off": True, "off_reason": r.get("activity") or "no school", "note": note})
                continue
            if kind == "journee":
                kind = "bloc"
            if not subject and r.get("matieres"):
                subject = self.env["homeschool.subject"]._by_csv_key(_split(r["matieres"])[0])
            name = r.get("activity") or kind
            vals = {
                "day_id": day.id, "kind": kind, "subject_id": subject.id, "name": name,
                "csv_key": (r.get("block") or "").strip() or False,
                "subject_codes": (r.get("matieres") or "").strip() or False,
                "sequence": 10 * (len(day.block_ids) + 1),
                "status": "done", "note": note,
                "duration_planned": int(r.get("minutes_total") or 0),
                "minutes_total": int(r["minutes_total"]) if (r.get("minutes_total") or "").strip() else False,
                "minutes_adult_present": int(r["minutes_adult_present"]) if (r.get("minutes_adult_present") or "").strip() else False,
            }
            existing = day.block_ids.filtered(lambda b: b.name == name and b.kind == kind)
            if existing:
                existing[0].write(vals)
            else:
                Block.create(vals)
        log.append("hours.csv: %d rows" % len(rows))
        return log

    # ------------------------------------------------------------------
    # UC-05 traces.csv
    # ------------------------------------------------------------------
    @api.model
    def import_traces(self, repo_path, student):
        log = []
        path = os.path.join(repo_path, "tracking", "traces.csv")
        if not os.path.exists(path):
            return log
        Item = self.env["homeschool.item"]
        Subject = self.env["homeschool.subject"]
        Attachment = self.env["ir.attachment"]
        rows = self._read_csv(path)
        for r in rows:
            code = r["trace_id"].strip()
            items = Item.browse()
            for c in _split(r.get("pda_ids")):
                it = Item._by_code(c)
                if it:
                    items |= it
                else:
                    log.append("traces.csv %s: unknown item %r" % (code, c))
            subjects = Subject.browse()
            for c in _split(r.get("matieres")):
                subjects |= Subject._by_csv_key(c)
            vals = {
                "name": r.get("title") or code,
                "date": fields.Date.to_date(r["date"].strip()),
                "student_id": student.id,
                "diffusion": "institutional" if (r.get("diffusion") or "").strip().upper() == "INSTITUTIONAL" else "internal",
                "artifact_path": r.get("artifact_path") or False,
                "item_codes": r.get("pda_ids") or False,
                "subject_codes": r.get("matieres") or False,
                "note": r.get("notes") or False,
                "subject_ids": [fields.Command.set(subjects.ids)],
                "item_ids": [fields.Command.set(items.ids)],
            }
            trace = self._upsert("homeschool.trace", "trace", code, vals)
            rel = (r.get("artifact_path") or "").strip()
            full = os.path.join(repo_path, rel) if rel else ""
            if rel and os.path.isfile(full) and not trace.attachment_ids.filtered(lambda a: a.name == os.path.basename(rel)):
                with open(full, "rb") as fh:
                    att = Attachment.create({"name": os.path.basename(rel), "raw": fh.read(), "res_model": "homeschool.trace", "res_id": trace.id})
                trace.attachment_ids |= att
            elif rel and not os.path.isfile(full):
                log.append("traces.csv %s: artifact not found %r" % (code, rel))
        log.append("traces.csv: %d rows" % len(rows))
        return log

    # ------------------------------------------------------------------
    # UC-06 coverage.csv (manual snapshot)
    # ------------------------------------------------------------------
    @api.model
    def import_coverage(self, repo_path):
        log = []
        path = os.path.join(repo_path, "tracking", "coverage.csv")
        if not os.path.exists(path):
            return log
        Item = self.env["homeschool.item"]
        rows = self._read_csv(path)
        for r in rows:
            item = Item._by_code(r["pda_id"].strip())
            if not item:
                log.append("coverage.csv %s: unknown item" % r["pda_id"])
                continue
            status = (r.get("status") or "").strip()
            vals = {
                "coverage_note": r.get("notes") or False,
                "coverage_date": fields.Date.to_date(r["date_updated"].strip()) if (r.get("date_updated") or "").strip() else False,
            }
            # only a non-default manual status becomes an override; computed statuses win otherwise
            vals["coverage_override"] = status if status in ("planned", "in_progress", "evidenced") and status != item.coverage_computed else False
            item.write(vals)
        log.append("coverage.csv: %d rows" % len(rows))
        return log

    # ------------------------------------------------------------------
    # UC-07 indicators
    # ------------------------------------------------------------------
    @api.model
    def import_indicators(self, repo_path, student):
        log = []
        Indicator = self.env["homeschool.indicator"]
        Value = self.env["homeschool.indicator.value"]
        defs = os.path.join(repo_path, "tracking", "indicateurs-definitions.csv")
        period = {"hebdo": "weekly", "quotidien": "daily", "jour": "daily", "mensuel": "monthly", "periodique": "periodic", "périodique": "periodic"}
        direction = {"hausse": "up", "baisse": "down", "stable": "stable"}
        if os.path.exists(defs):
            rows = self._read_csv(defs)
            for seq, r in enumerate(rows, start=1):
                code = (r.get("id") or "").strip()
                if not code:
                    continue
                self._upsert("homeschool.indicator", "indicator", code, {
                    "csv_sequence": seq,
                    "porte": r.get("porte") or False,
                    "name": r.get("libelle") or code,
                    "unit": r.get("unite") or False,
                    "period": period.get((r.get("cadence") or "").strip().lower(), "periodic"),
                    "cadence_raw": (r.get("cadence") or "").strip() or False,
                    "direction": direction.get((r.get("sens") or "").strip().lower().split("/")[0], False),
                    "sens_raw": (r.get("sens") or "").strip() or False,
                    "threshold": r.get("seuil") or False,
                    "source": r.get("source") or False,
                    "note": r.get("notes") or False,
                    "computed": "computed" in (r.get("notes") or "").lower() or code == "R1-ADULTE",
                })
            log.append("indicateurs-definitions.csv: %d rows" % len(rows))
        vals_path = os.path.join(repo_path, "tracking", "indicateurs.csv")
        if os.path.exists(vals_path):
            rows = self._read_csv(vals_path)
            n = 0
            for r in rows:
                ind = Indicator._by_code((r.get("id") or "").strip())
                if not ind:
                    log.append("indicateurs.csv: unknown indicator %r" % r.get("id"))
                    continue
                raw = (r.get("valeur") or "").strip()
                if raw == "":
                    continue  # a blank is not a zero
                d = fields.Date.to_date(r["date"].strip())
                existing = Value.search([("indicator_id", "=", ind.id), ("student_id", "=", student.id), ("date", "=", d)], limit=1)
                vals = {"value": float(raw.replace(",", ".")), "note": r.get("notes") or False}
                if existing:
                    existing.write(vals)
                else:
                    Value.create(dict(vals, indicator_id=ind.id, student_id=student.id, date=d))
                    n += 1
            log.append("indicateurs.csv: %d rows, %d new" % (len(rows), n))
        return log

    # ------------------------------------------------------------------
    # UC-08 journal week files
    # ------------------------------------------------------------------
    _DAY_HEADING = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s*$", re.M)

    @api.model
    def import_journal(self, repo_path, student):
        """tracking/journal/YYYY-Www/YYYY-Www.md — one entry per '### DATE' section, bullets verbatim."""
        log = []
        Journal = self.env["homeschool.journal"]
        Day = self.env["homeschool.day"]
        root = os.path.join(repo_path, "tracking", "journal")
        if not os.path.isdir(root):
            return log
        n = 0
        for week_dir in sorted(os.listdir(root)):
            week_file = os.path.join(root, week_dir, week_dir + ".md")
            if not os.path.isfile(week_file):
                continue
            with open(week_file, encoding="utf-8") as fh:
                text = fh.read()
            parts = self._DAY_HEADING.split(text)
            # parts = [preamble, date1, body1, date2, body2, ...]
            for i in range(1, len(parts) - 1, 2):
                d = fields.Date.to_date(parts[i])
                body = parts[i + 1].strip()
                bullets = [l[2:].strip() for l in body.splitlines() if l.startswith("- ")]
                well, badly, other = [], [], []
                for b in bullets:
                    low = b.lower()
                    if low.startswith("ce qui a marché"):
                        well.append(b.split(":", 1)[1].strip() if ":" in b else b)
                    elif low.startswith("ce qui a mal été"):
                        badly.append(b.split(":", 1)[1].strip() if ":" in b else b)
                    else:
                        other.append(b)
                day = Day._get_or_create(student, d)
                vals = {
                    "went_well": "\n".join(well) or False,
                    "went_badly": "\n".join(badly) or False,
                    "notes": "\n".join("- " + o for o in other) or False,
                }
                entry = Journal.search([("day_id", "=", day.id)], limit=1)
                if entry:
                    entry.with_context(journal_force_edit=True).write(vals)
                else:
                    Journal.create(dict(vals, day_id=day.id))
                    n += 1
        log.append("journal: %d new entries" % n)
        return log

    # ------------------------------------------------------------------
    # UC-09 material inventory (materiel/README.md table)
    # ------------------------------------------------------------------
    _INVENTORY_ROW = re.compile(r"^\|\s*(?P<name>[^|]+?)\s*\|\s*(?P<files>[^|]+?)\s*\|\s*(?P<usage>[^|]*?)\s*\|\s*$", re.M)
    _FILES_PATTERN = re.compile(r"`([^`]+)`")
    _ITEM_CODE = re.compile(r"\b([A-Z]{2,5}(?:-[A-Za-z0-9.]+)+)\b")

    @api.model
    def import_material(self, repo_path):
        log = []
        Material = self.env["homeschool.material"]
        Item = self.env["homeschool.item"]
        Attachment = self.env["ir.attachment"]
        readme = os.path.join(repo_path, "materiel", "README.md")
        if not os.path.isfile(readme):
            return log
        with open(readme, encoding="utf-8") as fh:
            text = fh.read()
        n = 0
        for m in self._INVENTORY_ROW.finditer(text):
            name, files, usage = m.group("name"), m.group("files"), m.group("usage")
            if name in ("Pièce", "") or set(name) <= {"-", " "}:
                continue
            paths = []
            for f in self._FILES_PATTERN.findall(files):
                # 'fiches/x.{html,pdf}' → fiches/x.html, fiches/x.pdf
                brace = re.match(r"^(.*)\{([^}]+)\}(.*)$", f)
                if brace:
                    paths += [brace.group(1) + ext + brace.group(3) for ext in brace.group(2).split(",")]
                else:
                    paths.append(f)
            pdf = next((p for p in paths if p.endswith(".pdf")), "")
            html = next((p for p in paths if p.endswith(".html")), "")
            kind = "fiche"
            top = (pdf or html).split("/")[0]
            kind = {"fiches": "fiche", "affiches": "poster", "lectures": "reading", "exercices": "exercise"}.get(top, "fiche")
            items = Item.browse()
            for code in set(self._ITEM_CODE.findall(usage)):
                it = Item._by_code(code)
                if it:
                    items |= it
            vals = {
                "kind": kind, "description": usage, "pdf_path": ("materiel/" + pdf) if pdf else False,
                "html_source_path": ("materiel/" + html) if html else False,
                "item_ids": [fields.Command.set(items.ids)],
                "subject_ids": [fields.Command.set(items.subject_id.ids)],
            }
            mat = Material.search([("name", "=", name)], limit=1)
            if mat:
                mat.write(vals)
            else:
                mat = Material.create(dict(vals, name=name))
                n += 1
            full = os.path.join(repo_path, "materiel", pdf) if pdf else ""
            if full and os.path.isfile(full) and not mat.pdf_attachment_id:
                with open(full, "rb") as fh:
                    mat.pdf_attachment_id = Attachment.create({"name": os.path.basename(pdf), "raw": fh.read(), "res_model": "homeschool.material", "res_id": mat.id})
        log.append("materiel/README.md: %d new" % n)
        return log

    # ------------------------------------------------------------------
    # everything
    # ------------------------------------------------------------------
    @api.model
    def import_all(self, repo_path, student, aliases=None):
        log = []
        log += self.import_projects(repo_path)
        log += self.import_curriculum(repo_path)
        log += self.import_coverage(repo_path)
        log += self.import_material(repo_path)
        log += self.import_hours(repo_path, student, aliases=aliases)
        log += self.import_traces(repo_path, student)
        log += self.import_indicators(repo_path, student)
        log += self.import_journal(repo_path, student)
        return log
