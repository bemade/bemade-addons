import re

from odoo import api, models
from odoo.exceptions import UserError

# UC-CAT-10 — markdown import. Parses the TTP vault FICHE + EVALUATION markdown
# (§-structured, Part A / Part B tables) into draft competency records.

TYPE_BY_EMOJI = {"\U0001f512": "security", "⚠": "critical", "▫": "standard"}
CODE_RE = re.compile(r"\b([A-Z]{2,4}-\d{1,3})\b")

DOMAIN_MAP = {
    "UNI": "Universel",
    "PRE": "Prérequis",
    "TST": "Tests d'analyse",
    "FIL": "Filtres en boîtier",
    "TET": "Têtes de contrôle",
    "MED": "Filtre à média",
    "ADO": "Adoucisseur",
    "CHA": "Charbon",
    "RO": "Osmose inverse",
    "BCL": "Boucle de distribution",
    "MAR": "Systèmes Mar-Cor",
}


def _clean(s):
    s = (s or "").strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)   # bold
    s = re.sub(r"`(.+?)`", r"\1", s)          # inline code
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)  # md links -> text
    return s.strip()


def _table_rows(lines):
    """Yield cell-lists for every markdown table row in *lines* (pipes)."""
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip("|").split("|")]
        yield cells


def _is_separator(cells):
    return all(set(c) <= set("-: ") for c in cells if c != "")


def _section(md, header_re):
    """Lines between the first '## ' header matching header_re and the next '## '."""
    out, capturing = [], False
    for ln in md.splitlines():
        if re.match(r"^##\s", ln):
            if capturing:
                break
            capturing = bool(header_re.search(ln))
            continue
        if capturing:
            out.append(ln)
    return out


class CbetCompetencyImport(models.Model):
    _inherit = "cbet.competency"

    # ------------------------------------------------------------------ parse
    @api.model
    def _parse_fiche_md(self, md):
        code = name = None
        for cells in _table_rows(md.splitlines()):
            if len(cells) < 2:
                continue
            key, val = _clean(cells[0]).lower(), _clean(cells[1])
            if key == "code" and not code:
                m = CODE_RE.search(val)
                if m:
                    code = m.group(1)
            elif key in ("nom", "name") and not name:
                name = val
        prereqs, seen = [], set()
        for cells in _table_rows(_section(md, re.compile(r"^##\s*2[.\s]"))):
            if not cells:
                continue
            # A single row may pack several codes ("TST-01 / TST-02 / ...").
            codes = CODE_RE.findall(cells[0])
            if not codes:
                continue
            joined = " ".join(cells)
            oblig = ("✅" in joined) or ("✓" in joined) or ("obligatoire" in joined.lower())
            for pcode in codes:
                if pcode in seen:
                    continue
                seen.add(pcode)
                prereqs.append({"code": pcode,
                                "type": "obligatoire" if oblig else "recommande"})
        return {"code": code, "name": name, "prerequisites": prereqs}

    @api.model
    def _parse_evaluation_md(self, md):
        criteria = []
        for cells in _table_rows(_section(md, re.compile(r"Partie A", re.I))):
            if len(cells) < 3 or _is_separator(cells) or not cells[0].strip().isdigit():
                continue
            ctype = next((t for emo, t in TYPE_BY_EMOJI.items() if emo in cells[1]), None)
            if not ctype:
                continue
            method, tol = cells[3] if len(cells) > 3 else "", ""
            if "·" in method:                    # "method · tolerance"
                method, tol = method.split("·", 1)
            criteria.append({"type": ctype, "text": _clean(cells[2]),
                             "method": _clean(method), "tolerance": _clean(tol)})

        # Essential questions: the "Items essentiels … questions <spec>" note,
        # where <spec> may be a range ("2 à 6"), a list ("1, 2, 5, 6, 7"), or a
        # mix ("1, 3 à 5, 8"). Ranges need not start at 1.
        ess_nums = set()
        note = re.search(r"[Ii]tems?\s+essentiels?.*", md)   # the note line only
        if note:
            after = re.search(r"questions?\s+([0-9][0-9,\s*àet\-–]*)",
                              note.group(0).replace("*", ""))
            if after:
                spec = after.group(1)
                for a, b in re.findall(r"(\d+)\s*[à\-–]\s*(\d+)", spec):
                    ess_nums.update(range(int(a), int(b) + 1))
                for n in re.findall(r"\d+", re.sub(r"\d+\s*[à\-–]\s*\d+", " ", spec)):
                    ess_nums.add(int(n))

        questions = []
        for cells in _table_rows(_section(md, re.compile(r"Partie B", re.I))):
            if len(cells) < 3 or _is_separator(cells) or not cells[0].strip().isdigit():
                continue
            num = int(cells[0])
            questions.append({
                "text": _clean(cells[1]),
                "expected_answer": _clean(cells[2]),
                "section_ref": _clean(cells[3]) if len(cells) > 3 else "",
                "essential": num in ess_nums,
            })
        return {"criteria": criteria, "questions": questions}

    # ---------------------------------------------------------------- import
    @api.model
    def _import_markdown(self, fiche_md, eval_md):
        """Create/update a draft competency from its FICHE + EVALUATION markdown.
        Idempotent by code. Returns (competency, prerequisite_specs)."""
        fiche = self._parse_fiche_md(fiche_md or "")
        parsed = self._parse_evaluation_md(eval_md or "")
        code = fiche["code"]
        if not code:
            raise UserError(self.env._("No competency code found in the FICHE markdown."))

        prefix = code.split("-")[0]
        Domain = self.env["cbet.domain"]
        domain = Domain.search([("code", "=", prefix)], limit=1) or Domain.create(
            {"code": prefix, "name": DOMAIN_MAP.get(prefix, prefix)})

        kind = "procedural" if parsed["criteria"] else "theoretical"
        vals = {"code": code, "name": fiche["name"] or code,
                "domain_id": domain.id, "kind": kind}

        comp = self.search([("code", "=ilike", code)], limit=1)
        if comp:
            comp.write(vals)
            comp.criterion_ids.unlink()
            comp.question_ids.unlink()
        else:
            comp = self.create(vals)

        unit = comp.unit_ids[:1]
        if parsed["criteria"]:
            self.env["cbet.criterion"].create([
                {"unit_id": unit.id, "sequence": (i + 1) * 10, "criterion_type": c["type"],
                 "text": c["text"], "verification_method": c["method"], "tolerance": c["tolerance"]}
                for i, c in enumerate(parsed["criteria"])
            ])
        if parsed["questions"]:
            self.env["cbet.question"].create([
                {"competency_id": comp.id, "sequence": (i + 1) * 10, "essential": q["essential"],
                 "text": q["text"], "expected_answer": q["expected_answer"],
                 "section_ref": q["section_ref"]}
                for i, q in enumerate(parsed["questions"])
            ])
        return comp, fiche["prerequisites"]

    @api.model
    def _analyze_markdown(self, fiche_md, eval_md):
        """Parse FICHE + EVALUATION WITHOUT writing anything — for dry runs.
        Returns a report dict (no side effects)."""
        fiche = self._parse_fiche_md(fiche_md or "")
        parsed = self._parse_evaluation_md(eval_md or "")
        code = fiche["code"]
        rep = {
            "code": code, "name": fiche["name"], "error": None, "warnings": [],
            "n_criteria": len(parsed["criteria"]),
            "n_questions": len(parsed["questions"]),
            "n_essential": sum(1 for q in parsed["questions"] if q["essential"]),
            "prereqs": fiche["prerequisites"], "kind": None,
            "domain_code": None, "exists": False,
        }
        if not code:
            rep["error"] = "no competency code found in FICHE"
            return rep
        rep["kind"] = "procedural" if parsed["criteria"] else "theoretical"
        rep["domain_code"] = code.split("-")[0]
        rep["exists"] = bool(self.search_count([("code", "=ilike", code)]))
        if not parsed["criteria"] and not parsed["questions"]:
            rep["warnings"].append("no criteria and no questions parsed")
        elif not parsed["questions"]:
            rep["warnings"].append("no Part B questions parsed")
        if rep["kind"] == "procedural" and parsed["questions"] and rep["n_essential"] == 0:
            rep["warnings"].append("no essential questions flagged")
        return rep

    @api.model
    def _link_prerequisites(self, code, prereq_specs):
        """Second-pass: create prerequisite edges once all competencies exist."""
        comp = self.search([("code", "=ilike", code)], limit=1)
        if not comp:
            return
        Edge = self.env["cbet.prerequisite"]
        for spec in prereq_specs:
            target = self.search([("code", "=ilike", spec["code"])], limit=1)
            if not target or target == comp:
                continue
            if Edge.search_count([("competency_id", "=", comp.id),
                                  ("prerequisite_id", "=", target.id)]):
                continue
            try:
                Edge.create({"competency_id": comp.id, "prerequisite_id": target.id,
                             "prereq_type": spec["type"]})
            except Exception:      # skip edges that would create a cycle
                continue
