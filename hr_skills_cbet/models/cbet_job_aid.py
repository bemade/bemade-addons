from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

MANAGER_GROUP = "hr_skills_cbet.group_cbet_manager"

SECTION_KINDS = [
    ("ppe", "PPE"),
    ("tools", "Tools"),
    ("stop", "STOP — escalate"),
    ("data", "Data to record"),
    ("photos", "Photos"),
    ("custom", "Other block"),
    ("phase", "Procedure phase"),
]


def _check_draft_for_trainer(env, competencies):
    """UC-CAT-08: below Manager, a job aid (and its sections and lines) may
    only change while its competency is in draft."""
    if env.su or env.user.has_group(MANAGER_GROUP):
        return
    published = competencies.filtered(lambda c: c.state != "draft")
    if published:
        raise AccessError(env._(
            "%(codes)s is published: its job aids are frozen. Ask a CBET Manager "
            "to reset it to draft before editing.",
            codes=", ".join(published.mapped("code"))))


class CbetJobAid(models.Model):
    """The laminated recto/verso field card of a competency.

    One per competency *variant* (a competency may ship one card per equipment
    family). Recto blocks and verso phases are sections; each section holds
    icon + text lines, and optionally a reference table (``note_html``).
    """

    _name = "cbet.job.aid"
    _description = "CBET Field Job Aid"
    _order = "competency_id, sequence, id"

    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    variant = fields.Char(
        help="Equipment family this card is specific to (e.g. RO). Empty for the "
             "competency's only card.",
    )
    name = fields.Char(compute="_compute_name", store=True)
    code = fields.Char(related="competency_id.code", string="Code")
    sequence = fields.Integer(default=10)
    section_ids = fields.One2many("cbet.job.aid.section", "job_aid_id", copy=True)
    # The same sections split by face for the editor (copy=False: section_ids
    # already carries them on duplicate).
    recto_section_ids = fields.One2many(
        "cbet.job.aid.section", "job_aid_id", string="Recto blocks",
        domain=[("face", "=", "recto")], copy=False,
    )
    verso_section_ids = fields.One2many(
        "cbet.job.aid.section", "job_aid_id", string="Verso phases",
        domain=[("face", "=", "verso")], copy=False,
    )
    section_count = fields.Integer(compute="_compute_section_count")
    active = fields.Boolean(default=True)
    competency_state = fields.Selection(related="competency_id.state")
    can_edit = fields.Boolean(compute="_compute_can_edit")

    @api.depends("competency_id.code", "competency_id.name", "variant")
    def _compute_name(self):
        for aid in self:
            name = "%s — %s" % (aid.competency_id.code or "", aid.competency_id.name or "")
            if aid.variant:
                name += " [%s]" % aid.variant
            aid.name = name.strip(" —")

    def _face_sections(self, face):
        """The sections of one face, in print order."""
        self.ensure_one()
        return self.section_ids.filtered(lambda s: s.face == face)

    @api.depends("section_ids")
    def _compute_section_count(self):
        for aid in self:
            aid.section_count = len(aid.section_ids)

    @api.depends("competency_id.state")
    @api.depends_context("uid")
    def _compute_can_edit(self):
        manager = self.env.user.has_group(MANAGER_GROUP)
        trainer = manager or self.env.user.has_group("hr_skills_cbet.group_cbet_trainer")
        for aid in self:
            aid.can_edit = manager or (trainer and aid.competency_id.state == "draft")

    # ------------------------------------------------------------------
    # UC-CAT-08 — trainer guard (draft competencies only) and authoring actions.
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        comps = self.env["cbet.competency"].browse(
            [v["competency_id"] for v in vals_list if v.get("competency_id")])
        _check_draft_for_trainer(self.env, comps)
        return super().create(vals_list)

    def write(self, vals):
        comps = self.competency_id
        if vals.get("competency_id"):
            comps |= comps.browse(vals["competency_id"])
        _check_draft_for_trainer(self.env, comps)
        return super().write(vals)

    def unlink(self):
        _check_draft_for_trainer(self.env, self.competency_id)
        return super().unlink()

    def _update_field_translations(self, field_name, translations, digest=None, source_lang=""):
        _check_draft_for_trainer(self.env, self.competency_id)
        return super()._update_field_translations(
            field_name, translations, digest=digest, source_lang=source_lang)

    def action_preview_pdf(self):
        return self.env.ref("hr_skills_cbet.action_report_cbet_job_aid").report_action(self)

    def action_open_variant_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Duplicate as variant"),
            "res_model": "cbet.job.aid.variant.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_job_aid_id": self.id},
        }

    @api.constrains("competency_id", "variant", "active")
    def _check_variant_unique(self):
        # A unique constraint would let two empty variants through (NULLs are
        # distinct), so the one-card-per-variant rule is enforced here.
        for aid in self.filtered("active"):
            dup = self.search_count([
                ("id", "!=", aid.id),
                ("competency_id", "=", aid.competency_id.id),
                ("variant", "=", aid.variant or False),
            ])
            if dup:
                raise ValidationError(self.env._(
                    "Competency %(code)s already has a job aid for variant %(variant)s.",
                    code=aid.competency_id.code, variant=aid.variant or "—"))


class CbetJobAidSection(models.Model):
    _name = "cbet.job.aid.section"
    _description = "CBET Job Aid Section"
    _order = "sequence, id"
    _inherit = ["cbet.content.revision.mixin"]
    _revision_fields = ("note_html",)

    job_aid_id = fields.Many2one(
        "cbet.job.aid", required=True, ondelete="cascade", index=True,
    )
    competency_id = fields.Many2one(related="job_aid_id.competency_id", store=True)
    face = fields.Selection(
        [("recto", "Recto"), ("verso", "Verso")], required=True, default="recto",
    )
    kind = fields.Selection(SECTION_KINDS, required=True, default="custom")
    icon_id = fields.Many2one("cbet.icon", string="Icon", ondelete="set null")
    name = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    line_ids = fields.One2many("cbet.job.aid.line", "section_id", copy=True)
    line_count = fields.Integer(compute="_compute_line_count")
    line_preview = fields.Char(compute="_compute_line_preview", string="Lines")
    revision_ids = fields.One2many(
        "cbet.content.revision", "section_id", string="Revisions", readonly=True,
    )
    # Whole-document per language (sanitize=False keeps Odoo from switching the
    # field to term-based translation); the importer sanitizes what it writes.
    can_edit = fields.Boolean(related="job_aid_id.can_edit")
    note_html = fields.Html(
        string="Reference table / note", translate=True, sanitize=False,
        help="Free block printed under the lines — the reference tables some "
             "analysis cards carry.",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for section in self:
            section.line_count = len(section.line_ids)

    @api.depends("line_ids.text", "line_ids.sequence")
    def _compute_line_preview(self):
        for section in self:
            texts = [t.strip() for t in section.line_ids.mapped("text") if t and t.strip()]
            preview = " · ".join(texts)
            section.line_preview = preview if len(preview) <= 120 else preview[:117] + "…"

    def _revision_link_vals(self):
        self.ensure_one()
        return {"competency_id": self.job_aid_id.competency_id.id, "section_id": self.id}

    def _cbet_check_content_write(self, vals):
        comps = self.job_aid_id.competency_id
        if vals.get("job_aid_id"):
            comps |= self.env["cbet.job.aid"].browse(vals["job_aid_id"]).competency_id
        _check_draft_for_trainer(self.env, comps)

    @api.model_create_multi
    def create(self, vals_list):
        aids = self.env["cbet.job.aid"].browse(
            [v["job_aid_id"] for v in vals_list if v.get("job_aid_id")])
        _check_draft_for_trainer(self.env, aids.competency_id)
        return super().create(vals_list)

    def unlink(self):
        _check_draft_for_trainer(self.env, self.job_aid_id.competency_id)
        return super().unlink()


class CbetJobAidLine(models.Model):
    _name = "cbet.job.aid.line"
    _description = "CBET Job Aid Line"
    _order = "sequence, id"

    section_id = fields.Many2one(
        "cbet.job.aid.section", required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    icon_id = fields.Many2one("cbet.icon", string="Icon", ondelete="set null")
    text = fields.Text(translate=True)

    def _competencies(self, vals=None):
        comps = self.section_id.job_aid_id.competency_id
        if vals and vals.get("section_id"):
            comps |= self.env["cbet.job.aid.section"].browse(
                vals["section_id"]).job_aid_id.competency_id
        return comps

    @api.model_create_multi
    def create(self, vals_list):
        sections = self.env["cbet.job.aid.section"].browse(
            [v["section_id"] for v in vals_list if v.get("section_id")])
        _check_draft_for_trainer(self.env, sections.job_aid_id.competency_id)
        return super().create(vals_list)

    def write(self, vals):
        _check_draft_for_trainer(self.env, self._competencies(vals))
        return super().write(vals)

    def unlink(self):
        _check_draft_for_trainer(self.env, self._competencies())
        return super().unlink()

    def _update_field_translations(self, field_name, translations, digest=None, source_lang=""):
        _check_draft_for_trainer(self.env, self._competencies())
        return super()._update_field_translations(
            field_name, translations, digest=digest, source_lang=source_lang)
