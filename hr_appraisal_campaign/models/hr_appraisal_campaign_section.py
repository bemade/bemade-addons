from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrAppraisalCampaignSection(models.Model):
    _name = "hr.appraisal.campaign.section"
    _description = "Evaluation Section"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    scale_id = fields.Many2one(
        "hr.appraisal.campaign.scale", "Rating Scale", required=True, ondelete="restrict",
        default=lambda s: s.env["hr.appraisal.campaign.scale"].search([], limit=1))
    criterion_ids = fields.One2many("hr.appraisal.campaign.criterion", "section_id", "Criteria")
    criterion_count = fields.Integer(compute="_compute_criterion_count")
    threshold_ids = fields.One2many(
        "hr.appraisal.campaign.threshold", "section_id", "Thresholds",
        domain=[("campaign_id", "=", False)],
        help="Default thresholds of this section (points of the section's final total) "
        "copied by new campaigns.")

    @api.depends("criterion_ids")
    def _compute_criterion_count(self):
        for section in self:
            section.criterion_count = len(section.criterion_ids)


class HrAppraisalCampaignThreshold(models.Model):
    """« Level X from N points ». Without a campaign, a default: of a section, or of the
    scale (overall, no section). With a campaign, that campaign's own rule."""

    _name = "hr.appraisal.campaign.threshold"
    _description = "Evaluation Rating Threshold"
    _order = "campaign_id, section_id, min_score desc, id"

    campaign_id = fields.Many2one("hr.appraisal.campaign", ondelete="cascade", index=True)
    section_id = fields.Many2one(
        "hr.appraisal.campaign.section", ondelete="cascade", index=True,
        help="Empty: the overall (total) score.")
    scale_id = fields.Many2one(
        "hr.appraisal.campaign.scale", required=True, ondelete="cascade", index=True,
        compute="_compute_scale_id", store=True, readonly=False, precompute=True)
    level_id = fields.Many2one(
        "hr.appraisal.campaign.scale.level", "Rating Level", required=True, ondelete="cascade",
        domain="[('scale_id', '=', scale_id)]")
    min_score = fields.Integer("From (points)", required=True)

    @api.depends("campaign_id.scale_id", "section_id.scale_id")
    def _compute_scale_id(self):
        for threshold in self:
            threshold.scale_id = (
                threshold.campaign_id.scale_id or threshold.section_id.scale_id or threshold.scale_id)

    @api.constrains("level_id", "scale_id")
    def _check_level_scale(self):
        for threshold in self:
            if threshold.level_id.scale_id != threshold.scale_id:
                raise ValidationError(self.env._(
                    "The rating level %s does not belong to the scale %s.",
                    threshold.level_id.display_name, threshold.scale_id.display_name))
