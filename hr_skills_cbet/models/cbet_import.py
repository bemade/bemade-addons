import re

from odoo import api, models
from odoo.exceptions import UserError

# UC-CAT-10 — markdown import. Parses the TTP vault FICHE + EVALUATION markdown
# (§-structured, Part A / Part B tables) into draft competency records.

TYPE_BY_EMOJI = {"\U0001f512": "security", "⚠": "critical", "▫": "standard"}
CODE_RE = re.compile(r"\b([A-Z]{2,4}-\d{1,3})\b")

# Domain names, (English, French). The vault's fiches name the domain in prose
# rather than as a reusable label, so the pairs live here.
DOMAIN_MAP = {
    "UNI": ("Universal", "Universel"),
    "PRE": ("Prerequisites", "Prérequis"),
    "TST": ("Analytical tests", "Tests d'analyse"),
    "FIL": ("Cartridge filters", "Filtres en boîtier"),
    "TET": ("Control heads", "Têtes de contrôle"),
    "MED": ("Media filter", "Filtre à média"),
    "ADO": ("Water softener", "Adoucisseur"),
    "CHA": ("Carbon", "Charbon"),
    "RO": ("Reverse osmosis", "Osmose inverse"),
    "BCL": ("Distribution loop", "Boucle de distribution"),
    "MAR": ("Mar-Cor systems", "Systèmes Mar-Cor"),
}


def _set_translations(record, langs, values):
    """Store *values* ({field: text}) as the translation of *record* in *langs*."""
    if not langs:
        return
    for field, value in values.items():
        record.update_field_translations(field, {lang: value for lang in langs})


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
    def _content_langs(self):
        """(source, french_codes) — where each language of the content goes.

        The plan is authored in French and translated to English, but Odoo's
        source language is en_US, so the English text is the base value and the
        French is stored as a translation. Every active French locale gets it,
        so an fr_FR-only database is not left reading English.
        """
        french = self.env["res.lang"].search(
            [("code", "=like", "fr%")]).mapped("code")
        return "en_US", french

    @api.model
    def _import_markdown(self, fiche_md, eval_md, fiche_en_md=None):
        """Create/update a competency from its FICHE + EVALUATION markdown.

        *fiche_en_md* is the optional English fiche (``FICHE_XXX-NN_EN.md``).
        Where an English text exists it becomes the source value and the French
        is stored as its translation; where it does not — the evaluation grids
        have no English edition yet — the French is written to both languages so
        nothing renders blank, and shows up as untranslated because the two
        languages hold the same string.

        Idempotent by code: identical markdown is a true no-op, so re-importing
        the vault does not churn rows. Change detection reads the *French*,
        because that is the source of record: revising the French sends a
        published competency back to draft (a Manager re-publishes, which bumps
        the version and freezes a fresh snapshot, UC-CAT-09), while supplying or
        correcting an English translation is applied in place.

        Returns (competency, prerequisite_specs).
        """
        fiche = self._parse_fiche_md(fiche_md or "")
        parsed = self._parse_evaluation_md(eval_md or "")
        fiche_en = self._parse_fiche_md(fiche_en_md) if fiche_en_md else None
        code = fiche["code"]
        if not code:
            raise UserError(self.env._("No competency code found in the FICHE markdown."))

        prefix = code.split("-")[0]
        domain = self._domain_for(prefix)

        kind = "procedural" if parsed["criteria"] else "theoretical"
        name_fr = fiche["name"] or code
        name_en = (fiche_en or {}).get("name") or name_fr
        vals = {"code": code, "name": name_en, "domain_id": domain.id, "kind": kind}

        _source, french = self._content_langs()
        comp = self.search([("code", "=ilike", code)], limit=1)
        if not comp:
            comp = self.create(vals)
            _set_translations(comp, french, {"name": name_fr})
            comp._write_imported_content(parsed)
            return comp, fiche["prerequisites"]

        if not comp._imported_content_differs(name_fr, kind, domain, parsed):
            # Nothing changed in the source language; still let a newly supplied
            # or corrected English text land, since that is a translation.
            comp.write({"name": name_en})
            _set_translations(comp, french, {"name": name_fr})
            return comp, fiche["prerequisites"]

        was_published = comp.state == "published"
        comp.write(vals)
        _set_translations(comp, french, {"name": name_fr})
        comp._write_imported_content(parsed)
        if was_published:
            comp.state = "draft"
            comp.message_post(body=self.env._(
                "Re-imported from markdown with changed content, so this "
                "competency went back to draft. Version %s still describes what "
                "was published; re-publish to issue a new version.",
                comp.version))
        return comp, fiche["prerequisites"]

    @api.model
    def _domain_for(self, prefix):
        """The competency's domain, named in both languages.

        An existing domain is corrected only while it still carries the name
        this table would have given it, so a name someone has edited by hand is
        left alone.
        """
        Domain = self.env["cbet.domain"]
        name_en, name_fr = DOMAIN_MAP.get(prefix, (prefix, prefix))
        french = self._content_langs()[1]
        domain = Domain.search([("code", "=", prefix)], limit=1)
        if not domain:
            domain = Domain.create({"code": prefix, "name": name_en})
            _set_translations(domain, french, {"name": name_fr})
            return domain
        if domain.with_context(lang="en_US").name in (name_en, name_fr):
            domain.write({"name": name_en})
            _set_translations(domain, french, {"name": name_fr})
        return domain

    def _imported_content_differs(self, name_fr, kind, domain, parsed):
        """Does the parsed markdown revise the *source* content?

        Read in French, because the plan is authored in French and translated
        afterwards: a new or corrected English text is a translation, not a
        revision, and must not send a published competency back to draft.
        Prerequisites are excluded too — they are linked in a second pass and
        are not part of the published snapshot an evaluation is run against.
        """
        self.ensure_one()
        _source, french = self._content_langs()
        comp = self.with_context(lang=french[0]) if french else self
        if (comp.name, comp.kind, comp.domain_id.id) != (name_fr, kind, domain.id):
            return True
        live_criteria = [
            (c.criterion_type, c.text, c.verification_method or "", c.tolerance or "")
            for c in comp.unit_ids[:1].criterion_ids.sorted("sequence")
        ]
        new_criteria = [
            (c["type"], c["text"], c["method"] or "", c["tolerance"] or "")
            for c in parsed["criteria"]
        ]
        if live_criteria != new_criteria:
            return True
        live_questions = [
            (q.text, q.expected_answer or "", q.section_ref or "", q.essential)
            for q in comp.question_ids.sorted("sequence")
        ]
        new_questions = [
            (q["text"], q["expected_answer"] or "", q["section_ref"] or "", q["essential"])
            for q in parsed["questions"]
        ]
        return live_questions != new_questions

    def _write_imported_content(self, parsed):
        """Replace the competency's criteria and questions with the parsed set.

        The grids have no English edition yet, so the French text is written to
        both languages: English readers see the French rather than a blank cell,
        and the pair being identical is what marks the row as untranslated.
        """
        self.ensure_one()
        _source, french = self._content_langs()
        self.criterion_ids.unlink()
        self.question_ids.unlink()
        unit = self.unit_ids[:1]
        if parsed["criteria"]:
            criteria = self.env["cbet.criterion"].create([
                {"unit_id": unit.id, "sequence": (i + 1) * 10, "criterion_type": c["type"],
                 "text": c["text"], "verification_method": c["method"], "tolerance": c["tolerance"]}
                for i, c in enumerate(parsed["criteria"])
            ])
            for record, c in zip(criteria, parsed["criteria"]):
                _set_translations(record, french, {
                    "text": c["text"],
                    "verification_method": c["method"],
                    "tolerance": c["tolerance"],
                })
        if parsed["questions"]:
            questions = self.env["cbet.question"].create([
                {"competency_id": self.id, "sequence": (i + 1) * 10, "essential": q["essential"],
                 "text": q["text"], "expected_answer": q["expected_answer"],
                 "section_ref": q["section_ref"]}
                for i, q in enumerate(parsed["questions"])
            ])
            for record, q in zip(questions, parsed["questions"]):
                _set_translations(record, french, {
                    "text": q["text"],
                    "expected_answer": q["expected_answer"],
                })

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
