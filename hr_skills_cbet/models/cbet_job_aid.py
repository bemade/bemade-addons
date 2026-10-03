from odoo import api, fields, models
from odoo.exceptions import ValidationError

SECTION_KINDS = [
    ("ppe", "PPE"),
    ("tools", "Tools"),
    ("stop", "STOP — escalate"),
    ("data", "Data to record"),
    ("photos", "Photos"),
    ("custom", "Other block"),
    ("phase", "Procedure phase"),
]


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
    section_count = fields.Integer(compute="_compute_section_count")
    active = fields.Boolean(default=True)

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
    # Whole-document per language (sanitize=False keeps Odoo from switching the
    # field to term-based translation); the importer sanitizes what it writes.
    note_html = fields.Html(
        string="Reference table / note", translate=True, sanitize=False,
        help="Free block printed under the lines — the reference tables some "
             "analysis cards carry.",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for section in self:
            section.line_count = len(section.line_ids)


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
