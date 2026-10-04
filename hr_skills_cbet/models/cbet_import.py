import base64
import mimetypes
import re
from html import unescape as _html_unescape

import markdown2

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.mail import html_sanitize

# UC-CAT-10 — markdown import. Parses the TTP vault documents — FICHE
# (§-structured), EVALUATION (Part A / Part B tables), PROCEDURE, JOB_AID and
# NOTES_DEMO — into draft competency records, so the vault can be loaded once
# and retired.

TYPE_BY_EMOJI = {"\U0001f512": "security", "⚠": "critical", "▫": "standard"}

# The vault ships each grid in French and, once translated, in English, so the
# structural markers the parser keys on are matched in either language.
PART_A_RE = re.compile(r"Part(?:ie)?\s+A", re.I)
PART_B_RE = re.compile(r"Part(?:ie)?\s+B", re.I)
ESSENTIAL_NOTE_RE = re.compile(r"(?:items?\s+essentiels?|essential\s+items?).*", re.I)
RANGE_RE = re.compile(r"(\d+)\s*(?:à|to|[-–])\s*(\d+)")
# "method · tolerance" is the intended separator; several grids use a spaced
# dash instead, which must not swallow the tolerance into the method.
DASH_SEPARATOR_RE = re.compile(r"\s[—–]\s")
# The type-tagged form some grids use in place of the "essential items …
# questions N" sentence. The tag sits on either side of the word depending on
# the language — "Items ⚠️ (2, 3, 4)" but "⚠️ items (2, 3, 4)" — so both the
# preceding and following text are captured and tested for the type emoji.
ITEMS_BY_TYPE_RE = re.compile(
    r"([^()\n]{0,6})items?\s*([^()\n]{0,12}?)\(([^)\n]*)\)", re.I)
CODE_RE = re.compile(r"\b([A-Z]{2,4}-\d{1,3})\b")
# The first cell of a criterion or question row is its number. Some grids mark
# the row in that same cell — the prerequisite grids star their essential
# questions as "1 ★" — so a trailing symbol must not make the row unreadable.
ROW_NUMBER_RE = re.compile(r"^(\d+)\s*[^\w\s]*$")

# Fiche sections are located by number ("## 9. …"), never by title.
SECTION_NUM_RE = re.compile(r"^##\s+(\d+)\.?(?:\s|$)")
H2_RE = re.compile(r"^##\s+(.*?)\s*$")
H1_RE = re.compile(r"^#\s+")
# "Sans objet" at the head of a section means the field stays empty.
NA_RE = re.compile(r"^\W*(?:sans objet|s\.\s?o\.|n/?a|not applicable|non applicable)\b", re.I)
# A range ("20–30 min", "1–2 h") reads as its first value.
DURATION_H_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)(?:\s*[-–à]\s*\d+(?:[.,]\d+)?)?\s*h(?:\s*(\d{1,2})\b)?", re.I)
DURATION_MIN_RE = re.compile(r"(\d+)(?:\s*[-–à]\s*\d+)?\s*min", re.I)
MONTHS_RE = re.compile(r"(\d+)\s*(?:mois|months?)\b", re.I)
YEARS_RE = re.compile(r"(\d+)\s*(?:ans?|years?)\b", re.I)

# Markdown → html.
MD_EXTRAS = ["tables", "fenced-code-blocks", "cuddled-lists", "strike"]
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
PAGE_BREAK_RE = re.compile(r"<div\s+class=\"pb\"\s*>\s*</div>", re.I)
# "- [x] item" → "- ☑ item": markdown2's task-list output is an <input>, which
# the html sanitizer strips, leaving the box blank.
CHECKBOX_RE = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)\[( |x|X)\]\s*", re.M)
IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Job aids.
TOKEN_RE = re.compile(r":([a-z]+-[a-z0-9-]+):")
LEADING_TOKEN_RE = re.compile(r"^\s*:([a-z]+-[a-z0-9-]+):\s*")

# The vault documents open with authoring notes (competency link, sources,
# see-also, "TWI format", note to the trainer…) between the H1 and the first
# section; in Odoo they are noise and are dropped on import. Only the scope
# notes of a procedure survive: a preamble paragraph is one when it starts,
# after the quote marker and an optional emoji, with one of these markers.
IDENTIFICATION_RE = re.compile(r"^##\s+Identification\b", re.I)
QUOTE_PREFIX_RE = re.compile(r"^\s*(?:>\s?)+")
RULE_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
SCOPE_NOTE_RE = re.compile(
    r"^(?:[^\w\s*`\[]+\s*)?(?:🎯|🛑|\*\*\s*(?:Portée|Hors scope|Hors portée"
    r"|Frontière de portée|Aucune intervention|Scope boundary|Scope|Out of scope"
    r"|No intervention))", re.I)
# Preamble notes are not always separated by a blank ">" line: a line opening
# with a label ("**Sources** :", "**Voir aussi :**", "Compétence :") or a scope
# marker starts a new paragraph of its own.
PREAMBLE_LABEL_RE = re.compile(
    r"^(?:[^\w\s*`\[]+\s*)?(?:\*\*[^*]{1,60}?\*\*\s*:|\*\*[^*]{1,60}?:\s*\*\*"
    r"|(?:Compétence(?: associée)?|(?:Associated )?[Cc]ompetency|Format)\s?:)")
# A ">" callout indented under a list item: markdown2 leaves the marker in the
# text, so the marker is dropped and the line stays the item's continuation.
NESTED_QUOTE_RE = re.compile(r"^([ \t]{2,})>[ \t]?", re.M)
# After the marker is dropped, an indented callout that follows a table (not a
# list item) is 4+ spaces of plain text, which markdown2 renders as a code
# block. Such a block is recognisable by its leading callout glyph and is
# re-rendered as a paragraph; real code/ASCII blocks never start with one.
CALLOUT_CODE_RE = re.compile(
    r"<pre><code>((?:ℹ️|ℹ|⚠️|⚠|📌|👉|➡️|🔒|🗓️|📖)\s.*?)</code></pre>", re.S)
RECTO_RE = re.compile(r"<!--\s*=*\s*RECTO\s*=*\s*-->")
VERSO_RE = re.compile(r"<!--\s*=*\s*VERSO\s*=*\s*-->")
META_RE = re.compile(r"<!--\s*job-aid\s*\|(.*?)-->", re.S)
BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+(?:\[[ xX]\]\s*)?(.*)$")
ITEM_SPLIT_RE = re.compile(r"\s*·\s*")
KIND_BY_TOKEN = {"sev-stop": "stop", "act-donnees": "data", "act-photo": "photos"}
KIND_BY_PREFIX = {"epi": "ppe", "outil": "tools"}
KIND_BY_WORD = [
    (("epi", "ppe"), "ppe"), (("outil", "tool"), "tools"), (("stop",), "stop"),
    (("donnée", "donnee", "data"), "data"), (("photo",), "photos"),
]
# Demo notes: the per-session log belongs to training lines, not the body.
LOG_SECTION_RE = re.compile(
    r"notes du formateur|trainer'?s notes|session notes|notes de session", re.I)

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

# Fiche fields written from the markdown, by kind of storage. The *translated*
# scalars take the English as source and the French as translation; the html
# bodies are whole documents per language; the plain values come from the
# French fiche only (they are language-independent).
FICHE_SCALARS = {
    "subtitle": ("subtitle",),
    "protocol_method": ("protocol", "method"),
    "protocol_place": ("protocol", "place"),
    "protocol_support": ("protocol", "support"),
    "protocol_start_conditions": ("protocol", "start_conditions"),
    "protocol_verbalization": ("protocol", "verbalization"),
    "protocol_min_evaluator_qualification": ("evaluator", "min_qualification"),
    "evaluator_independence": ("evaluator", "independence"),
    "maintenance_condition": ("validity", "maintenance_condition"),
    "recert_modality": ("validity", "recert_modality"),
    "recert_early_trigger": ("validity", "recert_early_trigger"),
    "learning_time": ("meta", "learning_time"),
    "field_frequency": ("meta", "field_frequency"),
    "common_pitfalls": ("meta", "common_pitfalls"),
}
FICHE_BODIES = ("execution_context", "knowledge_body", "safety_block", "tools_materials",
                "documents_required", "evidence_required", "references_body")
FICHE_PLAIN = {
    "protocol_duration": ("protocol", "duration"),
    "difficulty": ("meta", "difficulty"),
}
DOC_BODIES = {"PROCEDURE": "procedure_body", "NOTES_DEMO": "demo_notes_body"}


def _set_translations(record, langs, values):
    """Store *values* ({field: text}) as the translation of *record* in *langs*."""
    if not langs:
        return
    for field, value in values.items():
        record.update_field_translations(field, {lang: value for lang in langs})


def _set_body_translations(record, langs, values):
    """Same for the whole-document html bodies, written per language."""
    for lang in langs:
        record.with_context(lang=lang).write(values)


def _numbers_in(spec):
    """The set of question numbers a spec names, expanding any ranges."""
    found = set()
    for a, b in re.findall(RANGE_RE, spec):
        found.update(range(int(a), int(b) + 1))
    for n in re.findall(r"\d+", re.sub(RANGE_RE, " ", spec)):
        found.add(int(n))
    return found


def _part_b_columns(rows):
    """Locate the Part B columns from the header row.

    Most grids run "# | Question | Expected answer | Ref."; the recognition
    competencies insert an "Ess." column after the number. Falling back to fixed
    positions keeps a grid with no recognisable header working as before.
    """
    cols = {"question": 1, "answer": 2, "ref": 3, "essential": None}
    for cells in rows:
        lowered = [c.lower() for c in cells]
        if not any("question" in c for c in lowered):
            continue
        found = {"question": None, "answer": None, "ref": None, "essential": None}
        for i, c in enumerate(lowered):
            if found["question"] is None and "question" in c:
                found["question"] = i
            elif found["answer"] is None and ("réponse" in c or "reponse" in c
                                              or "answer" in c):
                found["answer"] = i
            elif found["ref"] is None and ("renvoi" in c or c.startswith("ref")):
                found["ref"] = i
            elif found["essential"] is None and c.startswith("ess"):
                found["essential"] = i
        if found["question"] is not None:
            return {k: (v if v is not None else cols.get(k)) if k != "essential" else v
                    for k, v in found.items()}
        break
    return cols


def _clean(s):
    """Plain text out of an inline markdown fragment (bold, code, links)."""
    s = (s or "").strip()
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)   # bold
    s = re.sub(r"`(.+?)`", r"\1", s)          # inline code
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)  # md links -> text
    return s.strip()


def _clean_inline(s):
    """_clean plus italics — for text that lands in Char/Text fields."""
    s = _clean(s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", s)
    s = re.sub(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", r"\1", s)
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


def _kv_rows(lines):
    """(key, value) pairs of a two-column markdown table, header row dropped."""
    rows, prev = [], None
    for cells in _table_rows(lines):
        if _is_separator(cells):
            prev = None            # the row before the separator was the header
            continue
        if prev is not None:
            rows.append(prev)
        prev = cells
    if prev is not None:
        rows.append(prev)
    return [(_clean(c[0]).lower(), c[1] if len(c) > 1 else "") for c in rows if c]


def _kv(rows, *needles):
    """The value of the first row whose key contains one of *needles*."""
    for key, value in rows:
        if any(n in key for n in needles):
            return value
    return ""


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


def _numbered_sections(md):
    """{n: lines} for every '## N.' section of a fiche (up to the next '## ')."""
    out, current = {}, None
    for ln in md.splitlines():
        if re.match(r"^##\s", ln):
            m = SECTION_NUM_RE.match(ln)
            current = int(m.group(1)) if m else None
            if current is not None:
                out[current] = []
            continue
        if current is not None:
            out[current].append(ln)
    return out


def _section_md(lines):
    """The markdown of a section body, minus the '---' rulers between sections."""
    return "\n".join(ln for ln in lines if ln.strip() != "---").strip()


def _is_na(md):
    return bool(NA_RE.match(_clean_inline(md.strip().splitlines()[0] if md.strip() else "")))


def _after_h1(md):
    """Everything after the document's H1 (the title is the record's name)."""
    lines = md.splitlines()
    for i, ln in enumerate(lines):
        if H1_RE.match(ln):
            return "\n".join(lines[i + 1:])
    return md


def _split_preamble(body, heading_re=H2_RE):
    """(preamble lines, rest lines) around the first heading matching
    *heading_re*; no such heading → no preamble, the body is left whole."""
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        if heading_re.match(ln):
            return lines[:i], lines[i:]
    return [], lines


def _preamble_paragraphs(lines):
    """Paragraphs of a preamble, quote markers stripped: blank lines and blank
    ``>`` lines separate them, so does a line opening with a label or a scope
    marker; horizontal rules are dropped."""
    paragraphs, current = [], []
    for ln in lines:
        text = QUOTE_PREFIX_RE.sub("", ln).rstrip()
        if not text.strip() or RULE_RE.match(text):
            if current:
                paragraphs.append(current)
            current = []
            continue
        if current and (SCOPE_NOTE_RE.match(text.strip()) or PREAMBLE_LABEL_RE.match(text.strip())):
            paragraphs.append(current)
            current = []
        current.append(text)
    if current:
        paragraphs.append(current)
    return paragraphs


def _is_scope_note(paragraph):
    return bool(SCOPE_NOTE_RE.match(paragraph[0].strip()))


def _insert_after_first_paragraph(rest, block):
    """*rest* starts with a heading: *block* goes after the first paragraph
    under it, or directly under the heading when a heading/rule/end comes first."""
    i = 1
    while i < len(rest) and not rest[i].strip():
        i += 1
    if i < len(rest) and not (rest[i].lstrip().startswith("#") or RULE_RE.match(rest[i])):
        while i < len(rest) and rest[i].strip():
            i += 1
    else:
        i = 1
    return rest[:i] + [""] + block + [""] + rest[i:]


def _strip_procedure_preamble(body):
    """Drop the authoring preamble of a procedure, keeping its scope notes as a
    blockquote right after the first section's first paragraph."""
    preamble, rest = _split_preamble(body)
    if not preamble:
        return body
    block = []
    for paragraph in filter(_is_scope_note, _preamble_paragraphs(preamble)):
        if block:
            block.append(">")
        block.extend("> " + ln for ln in paragraph)
    if block:
        rest = _insert_after_first_paragraph(rest, block)
    return "\n".join(rest)


def _md_to_html(md):
    """markdown → sanitized html. The only place html is produced from text."""
    if not md or not md.strip():
        return ""
    md = HTML_COMMENT_RE.sub("", md)
    md = PAGE_BREAK_RE.sub("", md)
    md = NESTED_QUOTE_RE.sub(r"\1", md)
    md = CHECKBOX_RE.sub(
        lambda m: m.group(1) + ("☑ " if m.group(2).lower() == "x" else "☐ "), md)
    html = markdown2.markdown(md, extras=MD_EXTRAS)
    html = CALLOUT_CODE_RE.sub(
        lambda m: markdown2.markdown(_html_unescape(m.group(1)).strip(), extras=MD_EXTRAS),
        html)
    html = html_sanitize(
        html, silent=True, sanitize_tags=True, sanitize_attributes=True,
        sanitize_style=False, sanitize_form=True, strip_style=False, strip_classes=False)
    return (html or "").strip()


def _inline_images(md, image_loader, warnings):
    """Rewrite relative image links to data URIs when the archive holds the file."""
    def repl(m):
        alt, src = m.group(1), m.group(2)
        if re.match(r"^(?:https?:|data:|/)", src, re.I):
            return m.group(0)
        data = image_loader(src) if image_loader else None
        if not data:
            warnings.append("image not found in archive: %s" % src)
            return m.group(0)
        mime = mimetypes.guess_type(src)[0] or "image/png"
        return "![%s](data:%s;base64,%s)" % (alt, mime, base64.b64encode(data).decode())
    return IMG_RE.sub(repl, md)


class CbetCompetencyImport(models.Model):
    _inherit = "cbet.competency"

    # ------------------------------------------------------------ value maps
    @api.model
    def _parse_duration_hours(self, text):
        """'~45 min', '1 h 30', '90 min incluant…' → hours; 0.0 when unreadable."""
        text = _clean_inline(text or "")
        mh, mm = DURATION_H_RE.search(text), DURATION_MIN_RE.search(text)
        if mh and (not mm or mh.start() <= mm.start()):
            hours = float(mh.group(1).replace(",", "."))
            return hours + (int(mh.group(2)) / 60.0 if mh.group(2) else 0.0)
        if mm:
            return int(mm.group(1)) / 60.0
        return 0.0

    @api.model
    def _parse_validity_months(self, text):
        """'12 mois' / '24 months' / '2 ans' → months; None when unreadable."""
        text = _clean_inline(text or "")
        m = MONTHS_RE.search(text)
        if m:
            return int(m.group(1))
        m = YEARS_RE.search(text)
        if m:
            return int(m.group(1)) * 12
        return None

    @api.model
    def _parse_difficulty(self, text):
        text = _clean_inline(text or "").lower()
        if not text:
            return None
        if any(w in text for w in ("élev", "elev", "fort", "high", "hard", "difficile")):
            return "high"
        if any(w in text for w in ("moyen", "medium", "moderate")):
            return "medium"
        return "low"

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
        sections = _numbered_sections(md)

        prereqs, seen = [], set()
        for cells in _table_rows(sections.get(2, [])):
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

        # The optional classification blockquote right under the H1.
        subtitle, after_h1 = "", False
        for ln in md.splitlines():
            if H1_RE.match(ln):
                after_h1 = True
                continue
            if not after_h1 or not ln.strip():
                continue
            if ln.startswith(">"):
                subtitle = (subtitle + " " + ln.lstrip("> ").strip()).strip()
                continue
            break
        subtitle = _clean_inline(subtitle)

        def body(n):
            text = _section_md(sections.get(n, []))
            return "" if _is_na(text) else _md_to_html(text)

        def scalar(n, *needles):
            return _clean_inline(_kv(_kv_rows(sections.get(n, [])), *needles))

        protocol_rows = _kv_rows(sections.get(9, []))
        method = _clean_inline(_kv(protocol_rows, "méthode", "methode", "method"))
        mode = _clean_inline(_kv(protocol_rows, "mode opératoire", "mode operatoire",
                                 "operating mode"))
        if mode:
            # The template's optional "Mode opératoire" row has no field of
            # its own; it is the method's sequence, so it rides with it.
            method = (method + " — " + mode).strip(" —")
        quiz = _clean_inline(_kv(protocol_rows, "quiz"))
        if quiz:
            # Same for the optional "Quiz de récupération" row.
            method = (method + " — Quiz : " + quiz).strip(" —")
        return {
            "code": code, "name": name, "prerequisites": prereqs,
            "subtitle": subtitle,
            "execution_context": body(1),
            "knowledge_body": body(3),
            "safety_block": body(4),
            "tools_materials": body(5),
            "documents_required": body(6),
            "evidence_required": body(11),
            "references_body": body(14),
            "protocol": {
                "method": method,
                "place": scalar(9, "lieu", "location", "place"),
                "duration": self._parse_duration_hours(
                    _kv(protocol_rows, "durée", "duree", "duration")),
                "start_conditions": scalar(9, "conditions de départ", "conditions de depart",
                                           "starting condition", "start condition",
                                           "initial condition"),
                "support": scalar(9, "accompagnement", "support", "assistance"),
                "verbalization": scalar(9, "verbalisation", "verbalization"),
            },
            "evaluator": {
                "min_qualification": scalar(10, "niveau", "level", "qualification"),
                "independence": scalar(10, "indépendance", "independance", "independence"),
            },
            "validity": {
                "months": self._parse_validity_months(
                    _kv(_kv_rows(sections.get(12, [])), "validité", "validite", "validity")),
                "maintenance_condition": scalar(12, "maintien", "maintenance"),
                "recert_modality": scalar(12, "modalité", "modalite", "method", "modality"),
                "recert_early_trigger": scalar(12, "déclencheur", "declencheur", "trigger"),
            },
            "meta": {
                "field_frequency": scalar(13, "fréquence", "frequence", "frequency"),
                "difficulty": self._parse_difficulty(
                    _kv(_kv_rows(sections.get(13, [])), "difficult")),
                "learning_time": scalar(13, "temps", "time", "learning"),
                "common_pitfalls": scalar(13, "pièges", "pieges", "pitfall", "trap"),
            },
        }

    @api.model
    def _parse_evaluation_md(self, md):
        criteria = []
        for cells in _table_rows(_section(md, PART_A_RE)):
            if (len(cells) < 3 or _is_separator(cells)
                    or not ROW_NUMBER_RE.match(cells[0].strip())):
                continue
            ctype = next((t for emo, t in TYPE_BY_EMOJI.items() if emo in cells[1]), None)
            if not ctype:
                continue
            method, tol = cells[3] if len(cells) > 3 else "", ""
            if "·" in method:                    # "method · tolerance"
                method, tol = method.split("·", 1)
            elif DASH_SEPARATOR_RE.search(method):
                # Some grids were written with a spaced dash instead of the
                # middle dot. Without this the whole cell lands in the method
                # and the criterion imports with no tolerance at all.
                method, tol = DASH_SEPARATOR_RE.split(method, maxsplit=1)
            criteria.append({"type": ctype, "text": _clean(cells[2]),
                             "method": _clean(method), "tolerance": _clean(tol)})

        # Essential questions: the "Items essentiels … questions <spec>" note.
        # <spec> is written freely — a range ("2 à 6" / "2 to 6"), a list
        # ("1, 2, 5"), individual items ("Q1, Q2, Q6 et Q7"), or a mix joined by
        # "et"/"and" — so take everything up to the trailing parenthetical or
        # sentence end and read the numbers out of it rather than trying to
        # enumerate the connectives.
        ess_nums = set()
        note = re.search(ESSENTIAL_NOTE_RE, md)   # the note line only
        if note:
            after = re.search(r"questions?\s+(.*)", note.group(0).replace("*", ""))
            if after:
                spec = re.split(r"[(.]", after.group(1))[0]
                ess_nums |= _numbers_in(spec)

        if not ess_nums:
            # Some grids skip that sentence and tag the items by type instead —
            # "Items ⚠️ (2, 3, 4)" / "Items 🔒 / ⚠️ (1–8)", with the ▫️ ones
            # listed the same way. Read the security/critical groups and ignore
            # the standard ones, so the essential gate is not silently empty.
            for before, after, body in ITEMS_BY_TYPE_RE.findall(
                    "\n".join(_section(md, PART_B_RE)).replace("*", "")):
                tag = before + after
                if "▫" in tag or not re.search(r"[\U0001f512⚠]", tag):
                    continue
                ess_nums |= _numbers_in(body)

        # Part B columns are not in the same order everywhere: the recognition
        # competencies carry an extra "Ess." column between the number and the
        # question. Read the header rather than counting positions, or the
        # question text ends up holding that column's emoji.
        part_b = list(_table_rows(_section(md, PART_B_RE)))
        cols = _part_b_columns(part_b)

        questions = []
        for cells in part_b:
            lead = ROW_NUMBER_RE.match(cells[0].strip()) if cells else None
            if len(cells) < 3 or _is_separator(cells) or not lead:
                continue
            num = int(lead.group(1))
            if cols["essential"] is not None and len(cells) > cols["essential"]:
                # An explicit per-row type marker beats the summary note.
                ess_nums.discard(num)
                if re.search(r"[\U0001f512⚠]", cells[cols["essential"]]):
                    ess_nums.add(num)
            def cell(name, default=""):
                i = cols[name]
                return _clean(cells[i]) if i is not None and len(cells) > i else default

            questions.append({
                "text": cell("question"),
                "expected_answer": cell("answer"),
                "section_ref": cell("ref"),
                "essential": num in ess_nums,
            })
        return {"criteria": criteria, "questions": questions}

    @api.model
    def _parse_procedure_md(self, md, image_loader=None):
        """PROCEDURE → {html, warnings}: everything after the H1 but the
        authoring preamble (scope notes kept under the Objective), images
        inlined as data URIs when *image_loader(relative_path)* returns their
        bytes."""
        warnings = []
        body = _strip_procedure_preamble(_after_h1(md or ""))
        body = _inline_images(body, image_loader, warnings)
        return {"html": _md_to_html(body), "warnings": warnings}

    @api.model
    def _parse_demo_notes_md(self, md):
        """NOTES_DEMO → {html, warnings}: from the Identification section on
        (the authoring preamble is dropped), except the per-session log
        section, which belongs to training lines."""
        kept, skipping = [], False
        _preamble, rest = _split_preamble(_after_h1(md or ""), IDENTIFICATION_RE)
        for ln in rest:
            if re.match(r"^##\s", ln):
                skipping = bool(LOG_SECTION_RE.search(ln))
            if not skipping:
                kept.append(ln)
        return {"html": _md_to_html("\n".join(kept)), "warnings": []}

    @api.model
    def _parse_job_aid_md(self, md, icons=None):
        """JOB_AID → {variant, recto: [section], verso: [section], warnings}.

        section = {kind, icon, name, lines: [{icon, text}], note_html}. Icons
        are catalog tokens (resolved to records when written). *icons* is the
        set of known tokens; it defaults to the catalog.
        """
        md = md or ""
        if icons is None:
            known = {t: i.emoji or "" for t, i in self.env["cbet.icon"]._by_token().items()}
        elif isinstance(icons, dict):
            known = dict(icons)
        else:
            known = dict.fromkeys(icons, "")
        warnings, variant = [], None
        meta = META_RE.search(md)
        if meta:
            for part in meta.group(1).split("|"):
                key, _sep, value = part.partition(":")
                if key.strip().lower() in ("variante", "variant"):
                    variant = value.strip() or None
        recto_m, verso_m = RECTO_RE.search(md), VERSO_RE.search(md)
        if not recto_m or not verso_m or verso_m.start() < recto_m.start():
            warnings.append("legacy layout (no RECTO/VERSO markers): kept as a single block")
            title = next((_clean_inline(ln[2:]) for ln in md.splitlines() if H1_RE.match(ln)), "")
            return {"variant": variant, "warnings": warnings, "verso": [],
                    "recto": [{"kind": "custom", "icon": None, "name": title,
                               "lines": [], "note_html": _md_to_html(md)}]}
        recto = self._parse_job_aid_face(md[recto_m.end():verso_m.start()], "recto",
                                         known, warnings)
        verso = self._parse_job_aid_face(md[verso_m.end():], "verso", known, warnings)
        return {"variant": variant, "recto": recto, "verso": verso, "warnings": warnings}

    @api.model
    def _parse_job_aid_face(self, md, face, known, warnings):
        md = PAGE_BREAK_RE.sub("", HTML_COMMENT_RE.sub("", md))
        sections, current, table, paragraph = [], None, [], []

        def close():
            if current is None:
                return
            note = "\n".join(paragraph + ([""] if paragraph and table else []) + table)
            current["note_html"] = _md_to_html(note)
            sections.append(current)

        def icon_of(text, where, anywhere=False):
            """A leading token (anywhere in the text for a heading) becomes
            the icon; any other token inside the text is replaced by its
            emoji so no ``:token:`` survives."""
            m = LEADING_TOKEN_RE.match(text) or (anywhere and TOKEN_RE.search(text))
            if not m:
                return None, inline_tokens(text, where)
            token = m.group(1)
            rest = (text[:m.start()] + " " + text[m.end():]).strip()
            if token not in known:
                warnings.append("unknown icon token :%s: in '%s'" % (token, where))
                token = None
            return token, inline_tokens(rest, where)

        def inline_tokens(text, where):
            def repl(m):
                token = m.group(1)
                if token not in known:
                    warnings.append("unknown icon token :%s: in '%s'" % (token, where))
                    return ""
                return known[token]
            return re.sub(r"[ \t]{2,}", " ", TOKEN_RE.sub(repl, text))

        def add_line(text):
            icon, rest = icon_of(text, current["name"])
            rest = _clean_inline(rest)
            if icon or rest:
                current["lines"].append({"icon": icon, "text": rest})

        for ln in md.splitlines():
            if H1_RE.match(ln):
                continue
            h2 = H2_RE.match(ln)
            if h2:
                close()
                table, paragraph = [], []
                token, name = icon_of(h2.group(1), "heading '%s'" % _clean_inline(
                    TOKEN_RE.sub("", h2.group(1))), anywhere=True)
                name = _clean_inline(name)
                current = {"kind": self._job_aid_kind(face, token, name), "icon": token,
                           "name": name, "lines": [], "note_html": ""}
                continue
            if current is None or not ln.strip():
                continue
            if ln.lstrip().startswith("|"):
                table.append(ln.strip())
                continue
            bullet = BULLET_RE.match(ln)
            if bullet:
                add_line(bullet.group(1))
            elif face == "recto":
                for item in ITEM_SPLIT_RE.split(ln.strip()):
                    if item:
                        add_line(item)
            else:
                paragraph.append(ln)
        close()
        return sections

    @api.model
    def _job_aid_kind(self, face, token, name):
        if face == "verso":
            return "phase"
        if token in KIND_BY_TOKEN:
            return KIND_BY_TOKEN[token]
        if token and token.split("-")[0] in KIND_BY_PREFIX:
            return KIND_BY_PREFIX[token.split("-")[0]]
        lowered = (name or "").lower()
        for words, kind in KIND_BY_WORD:
            if any(w in lowered for w in words):
                return kind
        return "custom"

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
    def _aligned_english(self, parsed, eval_en_md):
        """The English grid, but only when it lines up with the French one.

        The two editions are matched row by row, so a grid that has gained or
        lost a row in translation is discarded rather than silently pairing an
        English criterion with the wrong French one. The competency then keeps
        the French in both languages, exactly as if no translation existed.
        """
        if not eval_en_md:
            return None
        parsed_en = self._parse_evaluation_md(eval_en_md)
        if (len(parsed_en["criteria"]) != len(parsed["criteria"])
                or len(parsed_en["questions"]) != len(parsed["questions"])):
            return None
        return parsed_en

    @staticmethod
    def _job_aid_shape(parsed):
        return [[len(s["lines"]) for s in parsed[face]] for face in ("recto", "verso")]

    @api.model
    def _parse_documents(self, code, docs, warnings):
        """Parse the PROCEDURE / NOTES_DEMO / JOB_AID documents of one competency.

        Returns {bodies: {field: fr_html}, bodies_en: {field: en_html|None},
        job_aids: [(variant, parsed_fr, parsed_en_or_None)]}. Parser warnings
        are appended to *warnings* as (code, "KIND: message").
        """
        docs = docs or {}
        loader = docs.get("image_loader")
        bodies, bodies_en, job_aids = {}, {}, []

        def warn(kind, parsed):
            for w in parsed["warnings"]:
                warnings.append((code, "%s: %s" % (kind, w)))

        for kind, field in DOC_BODIES.items():
            parse = (self._parse_procedure_md if kind == "PROCEDURE"
                     else self._parse_demo_notes_md)
            if docs.get(kind):
                parsed = parse(docs[kind], loader) if kind == "PROCEDURE" else parse(docs[kind])
                warn(kind, parsed)
                bodies[field] = parsed["html"]
                bodies_en[field] = None
                if docs.get(kind + "_EN"):
                    parsed_en = (parse(docs[kind + "_EN"], loader) if kind == "PROCEDURE"
                                 else parse(docs[kind + "_EN"]))
                    warn(kind + "_EN", parsed_en)
                    bodies_en[field] = parsed_en["html"] or None

        known = set(self.env["cbet.icon"]._by_token())
        for spec in docs.get("JOB_AID") or []:
            parsed = self._parse_job_aid_md(spec.get("md") or "", known)
            warn("JOB_AID", parsed)
            variant = parsed["variant"] or spec.get("variant") or False
            parsed_en = None
            if spec.get("md_en"):
                parsed_en = self._parse_job_aid_md(spec["md_en"], known)
                if self._job_aid_shape(parsed_en) != self._job_aid_shape(parsed):
                    warnings.append((code, "JOB_AID: English edition does not align with the "
                                           "French (sections/lines differ); French kept in "
                                           "both languages"))
                    parsed_en = None
            job_aids.append((variant, parsed, parsed_en))
        return {"bodies": bodies, "bodies_en": bodies_en, "job_aids": job_aids}

    @api.model
    def _import_markdown(self, fiche_md, eval_md, fiche_en_md=None, eval_en_md=None,
                         docs=None, warnings=None):
        """Create/update a competency from its vault documents.

        *fiche_en_md* and *eval_en_md* are the optional English editions
        (``FICHE_XXX-NN_EN.md``, ``EVALUATION_XXX-NN_EN.md``). *docs* carries
        the other documents: ``PROCEDURE``, ``NOTES_DEMO`` (+ ``_EN`` twins),
        ``JOB_AID`` as a list of ``{variant, md, md_en}`` and an optional
        ``image_loader(relative_path) -> bytes``. Where an English text exists
        it becomes the source value and the French is stored as its
        translation; where it does not, the French is written to both languages
        so nothing renders blank, and shows up as untranslated because the two
        languages hold the same string.

        Idempotent by code: identical markdown is a true no-op, so re-importing
        the vault does not churn rows. Change detection reads the *French*,
        because that is the source of record: revising the French sends a
        published competency back to draft (a Manager re-publishes, which bumps
        the version and freezes a fresh snapshot, UC-CAT-09), while supplying or
        correcting an English translation is applied in place.

        Parser warnings go to *warnings* (a list of (code, message)) when given.
        Returns (competency, prerequisite_specs).
        """
        # The English edition is the source value and must land in en_US no
        # matter which language the importing user works in: a plain write
        # stores a translated field in the context language, so a French
        # manager would otherwise put the English into fr_CA (then overwrite
        # it with the French) and en_US would never see the English.
        self = self.with_context(lang=self._content_langs()[0])
        warnings = warnings if warnings is not None else []
        fiche = self._parse_fiche_md(fiche_md or "")
        parsed = self._parse_evaluation_md(eval_md or "")
        fiche_en = self._parse_fiche_md(fiche_en_md) if fiche_en_md else None
        parsed_en = self._aligned_english(parsed, eval_en_md)
        code = fiche["code"]
        if not code:
            raise UserError(self.env._("No competency code found in the FICHE markdown."))
        content = self._parse_documents(code, docs, warnings)

        prefix = code.split("-")[0]
        domain = self._domain_for(prefix)

        kind = "procedural" if parsed["criteria"] else "theoretical"
        name_fr = fiche["name"] or code
        name_en = (fiche_en or {}).get("name") or name_fr
        vals = {"code": code, "name": name_en, "domain_id": domain.id, "kind": kind}
        vals.update(self._fiche_plain_vals(fiche))

        _source, french = self._content_langs()
        comp = self.search([("code", "=ilike", code)], limit=1)
        if not comp:
            comp = self.create(vals)
            _set_translations(comp, french, {"name": name_fr})
            comp._write_imported_content(parsed, parsed_en)
            comp._write_imported_fiche(fiche, fiche_en)
            comp._write_imported_bodies(content)
            comp._write_imported_job_aids(content["job_aids"], rebuild=True)
            return comp, fiche["prerequisites"]

        if not comp._imported_content_differs(name_fr, kind, domain, parsed, fiche, content):
            # Nothing changed in the source language; still let a newly supplied
            # or corrected English text land, since that is a translation.
            comp.write({"name": name_en})
            _set_translations(comp, french, {"name": name_fr})
            comp._apply_english_grid(parsed_en)
            comp._write_imported_fiche(fiche, fiche_en)
            comp._write_imported_bodies(content)
            comp._write_imported_job_aids(content["job_aids"], rebuild=False)
            return comp, fiche["prerequisites"]

        was_published = comp.state == "published"
        comp.write(vals)
        _set_translations(comp, french, {"name": name_fr})
        comp._write_imported_content(parsed, parsed_en)
        comp._write_imported_fiche(fiche, fiche_en)
        comp._write_imported_bodies(content)
        comp._write_imported_job_aids(content["job_aids"], rebuild=True)
        if was_published:
            comp.state = "draft"
            comp.message_post(body=self.env._(
                "Re-imported from markdown with changed content, so this "
                "competency went back to draft. Version %s still describes what "
                "was published; re-publish to issue a new version.",
                comp.version))
        return comp, fiche["prerequisites"]

    @api.model
    def _fiche_plain_vals(self, fiche):
        """The language-independent fiche values (from the French edition)."""
        vals = {}
        for field, path in FICHE_PLAIN.items():
            value = fiche
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if field == "difficulty":
                vals[field] = value or False
            else:
                vals[field] = value or 0.0
        months = fiche["validity"]["months"]
        if months:
            vals["validity_months"] = months
        return vals

    @staticmethod
    def _fiche_value(fiche, path):
        value = fiche
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        return value or ""

    def _write_imported_fiche(self, fiche, fiche_en=None):
        """Write the fiche's translated scalars and html bodies, EN as source."""
        self.ensure_one()
        _source, french = self._content_langs()
        scalars_fr = {f: self._fiche_value(fiche, p) for f, p in FICHE_SCALARS.items()}
        scalars_en = ({f: self._fiche_value(fiche_en, p) for f, p in FICHE_SCALARS.items()}
                      if fiche_en else {})
        self.write({f: (scalars_en.get(f) or fr) or False for f, fr in scalars_fr.items()})
        _set_translations(self, french, {f: fr for f, fr in scalars_fr.items() if fr})
        bodies_fr = {f: fiche.get(f) or "" for f in FICHE_BODIES}
        bodies_en = {f: (fiche_en or {}).get(f) or "" for f in FICHE_BODIES}
        self.write({f: (bodies_en.get(f) or fr) or False for f, fr in bodies_fr.items()})
        _set_body_translations(self, french, {f: (fr or bodies_en.get(f)) or False
                                              for f, fr in bodies_fr.items()})

    def _write_imported_bodies(self, content):
        """Write the procedure / demo-notes bodies that were supplied."""
        self.ensure_one()
        if not content["bodies"]:
            return
        _source, french = self._content_langs()
        self.write({f: (content["bodies_en"].get(f) or fr) or False
                    for f, fr in content["bodies"].items()})
        _set_body_translations(self, french, {f: (fr or content["bodies_en"].get(f)) or False
                                              for f, fr in content["bodies"].items()})

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

    def _imported_content_differs(self, name_fr, kind, domain, parsed, fiche=None, content=None):
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
        if live_questions != new_questions:
            return True
        if fiche is not None:
            for field, path in FICHE_SCALARS.items():
                if (comp[field] or "") != self._fiche_value(fiche, path):
                    return True
            for field in FICHE_BODIES:
                if (comp[field] or "") != (fiche.get(field) or ""):
                    return True
            plain = self._fiche_plain_vals(fiche)
            for field, value in plain.items():
                if (comp[field] or (0.0 if field == "protocol_duration" else False)) != value:
                    return True
        if content is not None:
            for field, html in content["bodies"].items():
                if (comp[field] or "") != (html or ""):
                    return True
            for variant, parsed_aid, _en in content["job_aids"]:
                aid = comp.job_aid_ids.filtered(lambda a: (a.variant or False) == variant)
                if not aid or aid._structure() != self._job_aid_structure(parsed_aid):
                    return True
        return False

    # ------------------------------------------------------------- job aids
    @staticmethod
    def _job_aid_structure(parsed):
        """The comparable (French) shape of a parsed job aid."""
        return [
            (face, s["kind"], s["icon"], s["name"],
             [(ln["icon"], ln["text"]) for ln in s["lines"]], s["note_html"] or "")
            for face in ("recto", "verso") for s in parsed[face]
        ]

    def _write_imported_job_aids(self, job_aids, rebuild):
        """Create or refresh one cbet.job.aid per parsed variant.

        With *rebuild*, a job aid whose French structure changed is replaced
        (unlink + create); an unchanged one keeps its rows. Without it (the
        French is unchanged) only the English text is refreshed, in place.
        """
        self.ensure_one()
        _source, french = self._content_langs()
        Aid = self.env["cbet.job.aid"]
        icons = self.env["cbet.icon"]._by_token()
        for sequence, (variant, parsed, parsed_en) in enumerate(job_aids, start=1):
            aid = self.job_aid_ids.filtered(lambda a: (a.variant or False) == variant)
            structure = self._job_aid_structure(parsed)
            if aid and aid._structure() == structure:
                aid._apply_english_job_aid(parsed_en, french)
                continue
            if aid:
                if not rebuild:
                    continue
                aid.unlink()
            aid = Aid.create({"competency_id": self.id, "variant": variant or False,
                              "sequence": sequence * 10})
            source = parsed_en or parsed
            seq = 0
            for face in ("recto", "verso"):
                for s_fr, s_en in zip(parsed[face], source[face]):
                    seq += 10
                    section = self.env["cbet.job.aid.section"].create({
                        "job_aid_id": aid.id, "face": face, "kind": s_fr["kind"],
                        "icon_id": icons[s_fr["icon"]].id if s_fr["icon"] else False,
                        "name": s_en["name"] or s_fr["name"] or False, "sequence": seq,
                        "note_html": s_en["note_html"] or s_fr["note_html"] or False,
                    })
                    _set_translations(section, french, {"name": s_fr["name"] or False})
                    _set_body_translations(section, french, {
                        "note_html": (s_fr["note_html"] or s_en["note_html"]) or False})
                    lines = self.env["cbet.job.aid.line"].create([
                        {"section_id": section.id, "sequence": (i + 1) * 10,
                         "icon_id": icons[l_fr["icon"]].id if l_fr["icon"] else False,
                         "text": l_en["text"] or l_fr["text"] or False}
                        for i, (l_fr, l_en) in enumerate(zip(s_fr["lines"], s_en["lines"]))
                    ])
                    for line, l_fr in zip(lines, s_fr["lines"]):
                        _set_translations(line, french, {"text": l_fr["text"] or False})

    def _write_imported_content(self, parsed, parsed_en=None):
        """Replace the competency's criteria and questions with the parsed set.

        The French grid drives the structure — order, types, essential flags and
        section references all come from it. The English grid, when there is an
        aligned one, supplies the source-language wording; without it the French
        is written to both languages, so English readers see the French rather
        than a blank cell and the identical pair marks the row as untranslated.
        """
        self.ensure_one()
        _source, french = self._content_langs()
        source_criteria = (parsed_en or parsed)["criteria"]
        source_questions = (parsed_en or parsed)["questions"]
        self.criterion_ids.unlink()
        self.question_ids.unlink()
        unit = self.unit_ids[:1]
        if parsed["criteria"]:
            criteria = self.env["cbet.criterion"].create([
                {"unit_id": unit.id, "sequence": (i + 1) * 10, "criterion_type": c["type"],
                 "text": en["text"], "verification_method": en["method"],
                 "tolerance": en["tolerance"]}
                for i, (c, en) in enumerate(zip(parsed["criteria"], source_criteria))
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
                 "text": en["text"], "expected_answer": en["expected_answer"],
                 "section_ref": q["section_ref"]}
                for i, (q, en) in enumerate(zip(parsed["questions"], source_questions))
            ])
            for record, q in zip(questions, parsed["questions"]):
                _set_translations(record, french, {
                    "text": q["text"],
                    "expected_answer": q["expected_answer"],
                })

    def _apply_english_grid(self, parsed_en):
        """Move the existing rows onto an English wording, in place.

        Used when the French is unchanged but a translation has arrived: the
        rows keep their identity and their French, only the source-language text
        is refreshed.
        """
        self.ensure_one()
        if not parsed_en:
            return
        criteria = self.unit_ids[:1].criterion_ids.sorted("sequence")
        questions = self.question_ids.sorted("sequence")
        if (len(criteria) != len(parsed_en["criteria"])
                or len(questions) != len(parsed_en["questions"])):
            return
        for record, c in zip(criteria, parsed_en["criteria"]):
            record.with_context(lang="en_US").write({
                "text": c["text"],
                "verification_method": c["method"],
                "tolerance": c["tolerance"],
            })
        for record, q in zip(questions, parsed_en["questions"]):
            record.with_context(lang="en_US").write({
                "text": q["text"],
                "expected_answer": q["expected_answer"],
            })

    @api.model
    def _analyze_markdown(self, fiche_md, eval_md, docs=None):
        """Parse the documents WITHOUT writing anything — for dry runs.
        Returns a report dict (no side effects)."""
        self = self.with_context(lang=self._content_langs()[0])
        fiche = self._parse_fiche_md(fiche_md or "")
        parsed = self._parse_evaluation_md(eval_md or "")
        code = fiche["code"]
        docs = docs or {}
        rep = {
            "code": code, "name": fiche["name"], "error": None, "warnings": [],
            "n_criteria": len(parsed["criteria"]),
            "n_questions": len(parsed["questions"]),
            "n_essential": sum(1 for q in parsed["questions"] if q["essential"]),
            "prereqs": fiche["prerequisites"], "kind": None,
            "domain_code": None, "exists": False,
            "has_procedure": bool(docs.get("PROCEDURE")),
            "has_procedure_en": bool(docs.get("PROCEDURE_EN")),
            "has_notes": bool(docs.get("NOTES_DEMO")),
            "has_notes_en": bool(docs.get("NOTES_DEMO_EN")),
            "n_job_aids": len(docs.get("JOB_AID") or []),
            "n_job_aids_en": sum(1 for a in docs.get("JOB_AID") or [] if a.get("md_en")),
            "n_sections": sum(1 for n in range(1, 15) if fiche.get(
                {1: "execution_context", 3: "knowledge_body", 4: "safety_block",
                 5: "tools_materials", 6: "documents_required", 11: "evidence_required",
                 14: "references_body"}.get(n, ""))),
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
        if not fiche["validity"]["months"]:
            rep["warnings"].append("no validity period read from fiche §12 (default kept)")
        doc_warnings = []
        self._parse_documents(code, docs, doc_warnings)
        rep["warnings"] += [w for _c, w in doc_warnings]
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


class CbetJobAidImport(models.Model):
    _inherit = "cbet.job.aid"

    def _structure(self):
        """The comparable French shape of this job aid (see _job_aid_structure)."""
        self.ensure_one()
        _source, french = self.env["cbet.competency"]._content_langs()
        aid = self.with_context(lang=french[0]) if french else self
        return [
            (s.face, s.kind, s.icon_id.token or None, s.name or "",
             [(ln.icon_id.token or None, ln.text or "") for ln in s.line_ids.sorted("sequence")],
             s.note_html or "")
            for s in aid.section_ids.sorted("sequence")
        ]

    def _apply_english_job_aid(self, parsed_en, french):
        """Refresh the source-language (English) wording in place."""
        self.ensure_one()
        if not parsed_en:
            return
        sections = self.section_ids.sorted("sequence")
        flat = [s for face in ("recto", "verso") for s in parsed_en[face]]
        if len(flat) != len(sections):
            return
        for section, s_en in zip(sections, flat):
            section.with_context(lang="en_US").write({
                "name": s_en["name"] or section.with_context(lang=french[0] if french else "en_US").name or False,
                "note_html": s_en["note_html"] or False if s_en["note_html"] else section.note_html,
            })
            lines = section.line_ids.sorted("sequence")
            if len(lines) != len(s_en["lines"]):
                continue
            for line, l_en in zip(lines, s_en["lines"]):
                if l_en["text"]:
                    line.with_context(lang="en_US").write({"text": l_en["text"]})
