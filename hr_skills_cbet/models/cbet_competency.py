import hashlib
import json
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

CODE_RE = re.compile(r"^[A-Za-z]{2,4}-\d{1,3}$")

# The document bodies — whole html documents per language (UC-CAT-08).
BODY_FIELDS = (
    "execution_context",
    "knowledge_body",
    "safety_block",
    "tools_materials",
    "documents_required",
    "evidence_required",
    "references_body",
    "procedure_body",
    "demo_notes_body",
)
# What a CBET Trainer may change on a draft competency: the content, not the
# structure (criteria, questions, protocol, policy, lifecycle).
CONTENT_FIELDS = frozenset(BODY_FIELDS) | {"subtitle", "job_aid_ids"}
MANAGER_GROUP = "hr_skills_cbet.group_cbet_manager"


class CbetCompetency(models.Model):
    """UC-CAT-02 — a coded competency node (XXX-NN), not an hr.skill (D1)."""

    _name = "cbet.competency"
    _description = "CBET Competency"
    _order = "domain_id, code"
    _inherit = ["cbet.content.revision.mixin", "mail.thread"]
    _revision_fields = BODY_FIELDS

    code = fields.Char(required=True, tracking=True)
    name = fields.Char(required=True, translate=True, tracking=True)
    domain_id = fields.Many2one("cbet.domain", string="Domain", tracking=True)
    kind = fields.Selection(
        [
            ("procedural", "Procedural"),
            ("theoretical", "Theoretical"),
            ("orchestration", "Orchestration"),
        ],
        required=True,
        default="procedural",
        tracking=True,
        help="Theoretical competencies have no Part A (practical) requirement.",
    )
    active = fields.Boolean(default=True)

    # Lifecycle (UC-CAT-09).
    state = fields.Selection(
        [("draft", "Draft"), ("published", "Published")],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    version = fields.Char(default="0.1", copy=False, tracking=True)
    publish_date = fields.Date(copy=False, readonly=True)
    version_ids = fields.One2many(
        "cbet.competency.version", "competency_id", string="Version History"
    )

    # Catalog content (UC-CAT-02 AC3) — the fiche, section by section. The
    # html bodies are whole documents per language: sanitize=False keeps Odoo
    # from switching them to term-based translation (which would rebuild one
    # language from the other's structure); the importer sanitizes what it
    # writes.
    subtitle = fields.Char(
        translate=True,
        help="The classification line under the fiche title (e.g. recognition "
             "competency, demonstrated on real equipment).",
    )
    execution_context = fields.Html(translate=True, sanitize=False, string="§1 Execution context")
    knowledge_body = fields.Html(translate=True, sanitize=False, string="§3 Underlying knowledge")
    safety_block = fields.Html(translate=True, sanitize=False, string="§4 Safety")
    tools_materials = fields.Html(translate=True, sanitize=False, string="§5 Tools and materials")
    documents_required = fields.Html(
        translate=True, sanitize=False, string="§6 Documents required on site")
    evidence_required = fields.Html(
        translate=True, sanitize=False, string="§11 Evidence to retain")
    references_body = fields.Html(translate=True, sanitize=False, string="§14 References")
    # The operational documents (one rich-text body per language each).
    procedure_body = fields.Html(translate=True, sanitize=False, string="Procedure")
    demo_notes_body = fields.Html(
        translate=True, sanitize=False, string="Trainer demonstration notes",
        help="Everything of the trainer's demo notes except the per-session "
             "log, which is kept on training lines.",
    )
    job_aid_ids = fields.One2many(
        "cbet.job.aid", "competency_id", string="Job aids", copy=True,
    )
    job_aid_count = fields.Integer(string="Job aid count", compute="_compute_job_aid_count")
    has_procedure = fields.Boolean(compute="_compute_has_documents", store=True)
    has_job_aid = fields.Boolean(compute="_compute_has_documents", store=True)
    has_demo_notes = fields.Boolean(compute="_compute_has_documents", store=True)
    # Authoring (UC-CAT-08).
    revision_ids = fields.One2many(
        "cbet.content.revision", "competency_id", string="Revisions", readonly=True,
    )
    revision_count = fields.Integer(compute="_compute_revision_count")
    translation_status = fields.Selection(
        [
            ("none", "No content"),
            ("missing", "Translation missing"),
            ("done", "Translated"),
        ],
        compute="_compute_translation_status",
        search="_search_translation_status",
        help="Translation missing: at least one document body is the same in "
             "French and in English (the English edition was never written).",
    )
    can_edit_structure = fields.Boolean(compute="_compute_can_edit")
    can_edit_content = fields.Boolean(compute="_compute_can_edit")
    # Trainer metadata (§13).
    field_frequency = fields.Char(translate=True)
    difficulty = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
    )
    learning_time = fields.Char(translate=True)
    common_pitfalls = fields.Text(translate=True)

    # Children.
    unit_ids = fields.One2many("cbet.evaluation.unit", "competency_id", copy=True)
    question_ids = fields.One2many("cbet.question", "competency_id", copy=True)
    prerequisite_ids = fields.One2many(
        "cbet.prerequisite", "competency_id", string="Prerequisites", copy=True,
    )
    criterion_ids = fields.One2many(
        "cbet.criterion", "competency_id", string="All criteria (via units)",
    )

    # Evaluation policy (UC-CAT-04, UC-CAT-07).
    pass_threshold = fields.Float(
        string="Overall pass threshold (%)",
        default=80.0,
        help="Ratio of passed over ALL applicable criteria (sec+crit+standard, "
             "s.o. excluded). Security & critical criteria are a separate hard gate.",
    )
    validity_months = fields.Integer(
        string="Certification validity (months)",
        default=lambda self: self.env.company.cbet_default_validity_months,
    )
    reprise_deadline_days = fields.Integer(
        string="Retake deadline (days)",
        default=lambda self: self.env.company.cbet_reprise_deadline_days,
    )
    # Evaluation protocol (UC-CAT-07).
    protocol_method = fields.Char(translate=True)
    protocol_place = fields.Char(translate=True)
    protocol_duration = fields.Float(string="Protocol duration (hours)")
    protocol_support = fields.Char(string="Allowed support", translate=True)
    protocol_start_conditions = fields.Text(string="Starting conditions", translate=True)
    protocol_verbalization = fields.Text(string="Required verbalization", translate=True)
    protocol_min_evaluator_qualification = fields.Char(
        translate=True,
        help="Minimum qualification an evaluator must hold to evaluate this "
             "competency (policy value, set per competency).",
    )
    evaluator_independence = fields.Char(translate=True)
    # Validity and recertification (§12), beside validity_months.
    maintenance_condition = fields.Text(translate=True)
    recert_modality = fields.Text(string="Recertification modality", translate=True)
    recert_early_trigger = fields.Text(string="Early recertification trigger", translate=True)
    # Import guard (19.0.1.14.0): the content fingerprint as it stood right
    # after the last markdown import. A later import compares it with the live
    # fingerprint, so it never overwrites a competency edited in Odoo since.
    import_fingerprint = fields.Char(
        readonly=True, copy=False,
        help="Fingerprint of the content as it stood after the last markdown "
             "import. When the content no longer matches it, the competency was "
             "edited in Odoo and an import leaves it alone unless told to "
             "overwrite it.")
    imported_on = fields.Datetime(
        string="Last imported on", readonly=True, copy=False)
    designated_trainer_ids = fields.Many2many(
        "res.users",
        string="Designated trainers",
        help="UC-EVL-02 AC1: only these users may evaluate this competency "
             "(CBET Evaluator group necessary but not sufficient).",
    )

    @api.constrains("code")
    def _check_code(self):
        for comp in self:
            if not comp.code or not CODE_RE.match(comp.code):
                raise ValidationError(
                    self.env._("Competency code %s must match XXX-NN "
                               "(2–4 letters, dash, 1–3 digits).", comp.code or ""))
            # Case-insensitive uniqueness.
            dup = self.search_count([
                ("id", "!=", comp.id),
                ("code", "=ilike", comp.code),
            ])
            if dup:
                raise ValidationError(
                    self.env._("A competency with code %s already exists "
                               "(codes are case-insensitive).", comp.code))

    @api.depends("procedure_body", "demo_notes_body", "job_aid_ids", "job_aid_ids.active")
    def _compute_has_documents(self):
        for comp in self:
            comp.has_procedure = bool(comp.procedure_body)
            comp.has_job_aid = bool(comp.job_aid_ids)
            comp.has_demo_notes = bool(comp.demo_notes_body)

    @api.depends("job_aid_ids")
    def _compute_job_aid_count(self):
        for comp in self:
            comp.job_aid_count = len(comp.job_aid_ids)

    def action_view_job_aids(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("hr_skills_cbet.action_cbet_job_aid")
        action["domain"] = [("competency_id", "=", self.id)]
        action["context"] = {"default_competency_id": self.id}
        if len(self.job_aid_ids) == 1:
            action["view_mode"] = "form"
            action["views"] = [(False, "form")]
            action["res_id"] = self.job_aid_ids.id
        return action

    @api.depends("revision_ids")
    def _compute_revision_count(self):
        for comp in self:
            comp.revision_count = len(comp.revision_ids)

    @api.depends("state")
    @api.depends_context("uid")
    def _compute_can_edit(self):
        manager = self.env.user.has_group(MANAGER_GROUP)
        trainer = manager or self.env.user.has_group("hr_skills_cbet.group_cbet_trainer")
        for comp in self:
            comp.can_edit_structure = manager
            comp.can_edit_content = manager or (trainer and comp.state == "draft")

    # ------------------------------------------------------------------
    # UC-CAT-08 — translation status (whole-document bodies, see test_cat_17).
    # ------------------------------------------------------------------
    @api.model
    def _french_langs(self):
        return [code for code, _name in self.env["res.lang"].get_installed()
                if code.startswith("fr")]

    def _untranslated_bodies(self):
        """The body fields whose French edition is the English one (or that
        have no French at all), in any installed French language."""
        self.ensure_one()
        en = self.with_context(lang="en_US")
        missing = set()
        for lang in self._french_langs():
            fr = self.with_context(lang=lang)
            for fname in BODY_FIELDS:
                value_en = en[fname] or ""
                if value_en and (fr[fname] or "") == value_en:
                    missing.add(fname)
        return sorted(missing)

    @api.depends(*BODY_FIELDS)
    def _compute_translation_status(self):
        for comp in self:
            en = comp.with_context(lang="en_US")
            if not any(en[f] for f in BODY_FIELDS):
                comp.translation_status = "none"
            elif comp._untranslated_bodies():
                comp.translation_status = "missing"
            else:
                comp.translation_status = "done"

    def _search_translation_status(self, operator, value):
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(self.env._("Unsupported operator on translation status."))
        wanted = {value} if isinstance(value, str) or not value else set(value)
        matching = self.with_context(active_test=False).search([]).filtered(
            lambda c: c.translation_status in wanted)
        if operator in ("!=", "not in"):
            return [("id", "not in", matching.ids)]
        return [("id", "in", matching.ids)]

    # ------------------------------------------------------------------
    # UC-CAT-08 — trainer rights: content of a draft only.
    # ------------------------------------------------------------------
    def _revision_link_vals(self):
        self.ensure_one()
        return {"competency_id": self.id}

    def _cbet_check_content_write(self, vals):
        if self.env.su or self.env.user.has_group(MANAGER_GROUP):
            return
        structure = sorted(set(vals) - CONTENT_FIELDS)
        if structure:
            labels = [self._fields[f]._description_string(self.env) if f in self._fields else f
                      for f in structure]
            raise AccessError(self.env._(
                "Only a CBET Manager can change %(fields)s. A CBET Trainer edits "
                "the documents (sheet, procedure, job aids, demonstration notes) "
                "of a draft competency.", fields=", ".join(labels)))
        published = self.filtered(lambda c: c.state != "draft")
        if published:
            raise AccessError(self.env._(
                "%(codes)s is published: its documents are frozen. Ask a CBET "
                "Manager to reset it to draft before editing.",
                codes=", ".join(published.mapped("code"))))

    # ------------------------------------------------------------------
    # UC-CAT-08 — preview the documents (T2 reports, draft watermark included).
    # ------------------------------------------------------------------
    def _preview(self, xmlid):
        return self.env.ref(xmlid).report_action(self)

    def action_preview_fiche(self):
        return self._preview("hr_skills_cbet.action_report_cbet_fiche")

    def action_preview_procedure(self):
        return self._preview("hr_skills_cbet.action_report_cbet_procedure")

    def action_preview_demo_notes(self):
        return self._preview("hr_skills_cbet.action_report_cbet_demo_notes")

    @api.model_create_multi
    def create(self, vals_list):
        comps = super().create(vals_list)
        # UC-CAT-06 AC1: every competency has ≥1 unit (default unit auto-created).
        for comp in comps:
            if not comp.unit_ids:
                self.env["cbet.evaluation.unit"].create({
                    "competency_id": comp.id,
                    "name": self.env._("Default unit"),
                    "required": True,
                    "is_default": True,
                })
        return comps

    # ------------------------------------------------------------------
    # UC-CAT-03 AC4 — transitive obligatory closure.
    # ------------------------------------------------------------------
    def _obligatory_closure(self):
        """Return self plus every competency reachable through *obligatoire*
        prerequisite edges (transitive)."""
        result = self.browse()
        todo = self
        while todo:
            result |= todo
            nxt = todo.mapped("prerequisite_ids").filtered(
                lambda e: e.prereq_type == "obligatoire",
            ).mapped("prerequisite_id")
            todo = nxt - result
        return result

    # ------------------------------------------------------------------
    # UC-CAT-09 — publication workflow (Manager only).
    # ------------------------------------------------------------------
    def _bump_version(self):
        self.ensure_one()
        # First publication lands on 1.0; subsequent publications bump the minor.
        if not self.version_ids:
            return "1.0"
        try:
            major, minor = self.version.split(".")
            return "%s.%s" % (major, int(minor) + 1)
        except (ValueError, AttributeError):
            return "1.0"

    def action_open_publish_wizard(self):
        """The Publish button: a confirmation listing what changed since the
        last published version (UC-CAT-08 AC5)."""
        self.ensure_one()
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(self.env._("Only a CBET Manager can publish competencies."))
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Publish %s", self.code),
            "res_model": "cbet.publish.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_competency_id": self.id},
        }

    @api.model
    def _strip_ids(self, value):
        """The snapshot payload without the record ids, for comparisons."""
        if isinstance(value, dict):
            return {k: self._strip_ids(v) for k, v in value.items() if k != "id"}
        if isinstance(value, list):
            return [self._strip_ids(v) for v in value]
        return value

    def _content_fingerprint(self):
        """A stable digest of the competency's content, in every language.

        The published-snapshot payload (name, kind, protocol, validity, meta,
        fiche and document bodies, criteria, questions, job aids,
        prerequisites) read in the source language and in each active French
        locale — minus the record ids and the reading language, so recreated
        rows and the caller's language do not count as a change. Nothing that
        publishing or a plain import bookkeeping write touches is in it.
        """
        self.ensure_one()
        source, french = self._content_langs()
        Version = self.env["cbet.competency.version"]
        payload = {}
        for lang in dict.fromkeys([source] + list(french)):
            reading = self._strip_ids(Version.with_context(lang=lang)._snapshot_payload(
                self.with_context(lang=lang)))
            reading.pop("lang", None)
            payload[lang] = reading
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _edited_since_import(self):
        """True when the content no longer matches the last import's stamp —
        or when there is no stamp at all (created or never imported here)."""
        self.ensure_one()
        return (not self.import_fingerprint
                or self.import_fingerprint != self._content_fingerprint())

    def _stamp_import(self):
        """Record the current content as the last imported state."""
        now = fields.Datetime.now()
        for comp in self:
            comp.sudo().write({"import_fingerprint": comp._content_fingerprint(),
                               "imported_on": now})

    def _document_changes(self):
        """What changed since the last published version, per document —
        counts only: [{"label", "changed", "total"}]. ``None`` when the
        competency was never published. The live payload is read in the
        language the snapshot was taken in (a snapshot from before 1.11
        carries no language: the user's language is used, and a key the old
        snapshot never had is not counted as a change)."""
        self.ensure_one()
        last = self.version_ids.sorted(lambda v: (v.publish_date, v.id))[-1:]
        if not last:
            return None
        old = self._strip_ids(last.snapshot or {})
        if old.get("lang"):
            langs = [old["lang"]]
        else:
            # A snapshot from before 1.11 does not say which language it was
            # taken in: try the user's and the source language and keep the
            # reading with the fewest changes, so a French reviewer is not
            # told that every section of an English snapshot changed.
            langs = list(dict.fromkeys([self.env.lang or "en_US", "en_US"]))
        return min((self._document_changes_in(old, lang) for lang in langs),
                   key=lambda rows: sum(r["changed"] for r in rows))

    def _document_changes_in(self, old, lang):
        """``_document_changes`` for one language of the live payload."""
        Version = self.env["cbet.competency.version"].with_context(lang=lang)
        new = self._strip_ids(Version._snapshot_payload(self.with_context(lang=lang)))
        _ = self.env._

        def norm(value):
            if isinstance(value, dict):
                return {k: norm(v) for k, v in value.items() if k != "lang"}
            if isinstance(value, list):
                return [norm(v) for v in value]
            return value or None

        def changed_keys(keys):
            return sum(1 for k in keys if k in old and norm(old.get(k)) != norm(new.get(k)))

        fiche_keys = ("subtitle", "execution_context", "knowledge_body", "safety_block",
                      "tools_materials", "documents_required", "evidence_required",
                      "references_body", "protocol", "validity", "meta", "prerequisites")
        old_aids = {a.get("variant") or "": a for a in old.get("job_aids", [])}
        new_aids = {a.get("variant") or "": a for a in new.get("job_aids", [])}
        aids_changed = (0 if "job_aids" not in old else
                        sum(1 for v in set(old_aids) | set(new_aids)
                            if norm(old_aids.get(v)) != norm(new_aids.get(v))))
        old_crit = [c for u in old.get("units", []) for c in u.get("criteria", [])]
        new_crit = [c for u in new.get("units", []) for c in u.get("criteria", [])]
        crit_changed = sum(1 for a, b in zip(old_crit, new_crit) if a != b) \
            + abs(len(old_crit) - len(new_crit))
        old_q, new_q = old.get("questions", []), new.get("questions", [])
        q_changed = sum(1 for a, b in zip(old_q, new_q) if a != b) + abs(len(old_q) - len(new_q))
        return [
            {"label": _("Competency sheet"), "changed": changed_keys(fiche_keys),
             "total": len(fiche_keys)},
            {"label": _("Procedure"), "changed": changed_keys(("procedure_body",)), "total": 1},
            {"label": _("Job aids"), "changed": aids_changed,
             "total": max(len(old_aids), len(new_aids))},
            {"label": _("Demonstration notes"), "changed": changed_keys(("demo_notes_body",)),
             "total": 1},
            {"label": _("Criteria and questions"), "changed": crit_changed + q_changed,
             "total": len(new_crit) + len(new_q)},
        ]

    def action_publish(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(self.env._("Only a CBET Manager can publish competencies."))
        for comp in self:
            comp.version = comp._bump_version()
            comp.publish_date = fields.Date.context_today(comp)
            comp.state = "published"
            self.env["cbet.competency.version"]._snapshot(comp)
        return True

    def action_reset_to_draft(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise UserError(self.env._("Only a CBET Manager can change competency state."))
        self.state = "draft"
        return True
