from odoo import api, fields, models

COLORS = [
    ("danger", "Red"),
    ("warning", "Orange"),
    ("secondary", "Grey"),
    ("info", "Blue"),
    ("primary", "Purple"),
    ("success", "Green"),
]


class HrAppraisalCampaignScale(models.Model):
    _name = "hr.appraisal.campaign.scale"
    _description = "Evaluation Rating Scale"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    level_ids = fields.One2many("hr.appraisal.campaign.scale.level", "scale_id", "Levels", copy=True)
    level_count = fields.Integer(compute="_compute_values")
    min_value = fields.Integer(compute="_compute_values")
    max_value = fields.Integer("Highest Value", compute="_compute_values")
    section_ids = fields.One2many("hr.appraisal.campaign.section", "scale_id", "Sections")
    # defaults copied by every new campaign using this scale
    threshold_ids = fields.One2many(
        "hr.appraisal.campaign.threshold", "scale_id", "Overall Thresholds",
        domain=[("campaign_id", "=", False), ("section_id", "=", False)],
        help="Default overall thresholds of a new campaign (points of the final total).")
    default_target_score = fields.Integer(
        "Target Score", help="Default target score (overall points) of a new campaign.")
    default_alignment_gap = fields.Integer(
        "Alignment Gap", help="Default alignment gap of a new campaign: self and final totals "
        "within this many points are « aligned ».")

    @api.depends("level_ids.value")
    def _compute_values(self):
        for scale in self:
            values = scale.level_ids.mapped("value")
            scale.level_count = len(values)
            scale.min_value = min(values) if values else 0
            scale.max_value = max(values) if values else 0

    def _lowest_level(self):
        self.ensure_one()
        return self.level_ids.sorted("value")[:1]


class HrAppraisalCampaignScaleLevel(models.Model):
    _name = "hr.appraisal.campaign.scale.level"
    _description = "Evaluation Rating Level"
    _order = "scale_id, value, id"

    scale_id = fields.Many2one(
        "hr.appraisal.campaign.scale", required=True, ondelete="cascade", index=True)
    value = fields.Integer(required=True, help="The grade this level stands for (1, 2, 3…).")
    name = fields.Char(required=True, translate=True)
    color = fields.Selection(
        COLORS, "Badge Colour", help="Leave empty for an automatic colour (lowest red, highest green).")
    display_color = fields.Char(compute="_compute_display_color")

    _value_unique = models.Constraint(
        "UNIQUE(scale_id, value)", "Each level of a scale has its own value.")
    _value_positive = models.Constraint(
        "CHECK(value >= 1)", "Level values start at 1 (0 means « not graded »).")

    @api.depends("color", "value", "scale_id.level_ids.value")
    def _compute_display_color(self):
        for level in self:
            if level.color:
                level.display_color = level.color
                continue
            values = sorted(level.scale_id.level_ids.mapped("value"))
            if len(values) < 2 or level.value not in values:
                level.display_color = "secondary"
                continue
            ratio = values.index(level.value) / (len(values) - 1)
            if ratio == 0:
                level.display_color = "danger"
            elif ratio == 1:
                level.display_color = "success"
            elif ratio < 0.5:
                level.display_color = "warning"
            elif ratio == 0.5:
                level.display_color = "secondary"
            else:
                level.display_color = "info"

    @api.depends("value", "name")
    def _compute_display_name(self):
        for level in self:
            level.display_name = f"{level.value} – {level.name}"

    @api.model_create_multi
    def create(self, vals_list):
        levels = super().create(vals_list)
        # every criterion of the scale gets a word picture for the new level
        criteria = self.env["hr.appraisal.campaign.criterion"].with_context(active_test=False).search(
            [("scale_id", "in", levels.scale_id.ids)])
        criteria._sync_levels()
        return levels
