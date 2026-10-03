import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

TOKEN_RE = re.compile(r"^[a-z]+-[a-z0-9-]+$")

ICON_CATEGORIES = [
    ("epi", "PPE"),
    ("sev", "Severity"),
    ("act", "Action"),
    ("outil", "Tool"),
    ("item", "Consumable / item"),
    ("comp", "Component"),
]


class CbetIcon(models.Model):
    """The job-aid icon catalog: one row per `:category-name:` token.

    The field documents name their pictograms by token; the import resolves
    every token to a row here, so no token text survives in the content. The
    emoji is the interim preview, the SVG the printable asset (loaded later).
    """

    _name = "cbet.icon"
    _description = "CBET Job Aid Icon"
    _order = "category, token"

    token = fields.Char(required=True, help="Catalog token, e.g. epi-lunettes (without colons).")
    category = fields.Selection(
        ICON_CATEGORIES, compute="_compute_category", store=True, readonly=False,
        precompute=True,
    )
    name = fields.Char(required=True, translate=True)
    emoji = fields.Char(help="Interim preview used where the SVG is not available.")
    svg = fields.Binary(attachment=True, string="SVG")
    svg_filename = fields.Char()
    iso_ref = fields.Char(string="ISO reference", help='e.g. "ISO 7010 M004"')
    active = fields.Boolean(default=True)

    _token_uniq = models.Constraint(
        "unique(token)",
        "An icon with this token already exists.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("token"):
                vals["token"] = self._normalize_token(vals["token"])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("token"):
            vals = dict(vals, token=self._normalize_token(vals["token"]))
        return super().write(vals)

    @api.model
    def _normalize_token(self, token):
        return (token or "").strip().strip(":").lower()

    @api.constrains("token")
    def _check_token(self):
        for icon in self:
            if not TOKEN_RE.match(icon.token or ""):
                raise ValidationError(self.env._(
                    "Icon token %s must look like category-name (lowercase, dashes).",
                    icon.token or ""))

    @api.depends("token")
    def _compute_category(self):
        known = dict(ICON_CATEGORIES)
        for icon in self:
            prefix = (icon.token or "").strip(":").split("-")[0]
            icon.category = prefix if prefix in known else (icon.category or False)

    @api.depends("emoji", "name")
    def _compute_display_name(self):
        for icon in self:
            icon.display_name = " ".join(p for p in (icon.emoji, icon.name) if p)

    @api.model
    def _by_token(self):
        """{token: icon} over the whole catalog, archived rows included — an
        archived icon still resolves on import, it just is not offered."""
        return {icon.token: icon for icon in self.with_context(active_test=False).search([])}
