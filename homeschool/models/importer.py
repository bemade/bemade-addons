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
        return list(csv.DictReader(io.StringIO("\n".join(lines))))

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
            for r in rows:
                code = r["pda_id"].strip()
                if not code:
                    continue
                vals = {
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
            for r in rows:
                code = r["item_id"].strip()
                if not code:
                    continue
                self._upsert("homeschool.item", "item", code, {
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

        cov_path = os.path.join(cur, "covers.csv")
        if os.path.exists(cov_path):
            rows = self._read_csv(cov_path)
            for r in rows:
                internal = Item._by_code(r["internal_id"].strip())
                target = Item._by_code(r["covers_id"].strip())
                if not internal or not target:
                    log.append("covers.csv %s → %s: unknown item" % (r["internal_id"], r["covers_id"]))
                    continue
                for it in internal._descendants():
                    it.covers_ids |= target._descendants()
                    it.covers_basis = r.get("basis") or it.covers_basis
            log.append("covers.csv: %d rows" % len(rows))

        dep_path = os.path.join(cur, "deps-requires.csv")
        if os.path.exists(dep_path):
            rows = self._read_csv(dep_path)
            Dep = self.env["homeschool.item.dependency"]
            n = 0
            for r in rows:
                src = Item._by_code((r.get("from_id") or "").strip())
                dst = Item._by_code((r.get("to_id") or "").strip())
                if not src or not dst:
                    log.append("deps-requires.csv %s → %s: unknown item" % (r.get("from_id"), r.get("to_id")))
                    continue
                if not Dep.search([("from_item_id", "=", src.id), ("to_item_id", "=", dst.id)], limit=1):
                    Dep.create({"from_item_id": src.id, "to_item_id": dst.id, "basis": r.get("basis"),
                                "mode": r.get("mode"), "note": r.get("note")})
                    n += 1
            log.append("deps-requires.csv: %d rows, %d new edges" % (len(rows), n))
        return log
