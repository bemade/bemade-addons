from odoo import Command, api, fields, models


class HrAppraisalCampaignCriterion(models.Model):
    _name = "hr.appraisal.campaign.criterion"
    _description = "Evaluation Criterion"
    _order = "section_sequence, section_id, sequence, id"

    section_id = fields.Many2one(
        "hr.appraisal.campaign.section", "Section", required=True, ondelete="restrict", index=True)
    section_sequence = fields.Integer("Section Sequence", related="section_id.sequence", store=True)
    scale_id = fields.Many2one(related="section_id.scale_id", store=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True, translate=True)
    description = fields.Text(translate=True)
    level_ids = fields.One2many(
        "hr.appraisal.campaign.criterion.level", "criterion_id", "Word Pictures", copy=True)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        criteria = super().create(vals_list)
        criteria._sync_levels()
        return criteria

    def write(self, vals):
        res = super().write(vals)
        if "section_id" in vals:
            self._sync_levels()
        return res

    def _sync_levels(self):
        """One word-picture line per level of the criterion's scale."""
        for criterion in self:
            levels = criterion.scale_id.level_ids
            stale = criterion.level_ids.filtered(lambda line: line.level_id not in levels)
            missing = levels - criterion.level_ids.level_id
            commands = [Command.unlink(line.id) for line in stale]
            commands += [Command.create({"level_id": level.id}) for level in missing]
            if commands:
                criterion.level_ids = commands

    def _missing_pictures(self):
        """Criteria (of ``self``) without a word picture for some level of their scale."""
        return self.filtered(
            lambda c: c.level_ids.level_id != c.scale_id.level_ids
            or not all(c.level_ids.mapped("description")))


class HrAppraisalCampaignCriterionLevel(models.Model):
    _name = "hr.appraisal.campaign.criterion.level"
    _description = "Evaluation Criterion Word Picture"
    _order = "criterion_id, value, id"

    criterion_id = fields.Many2one(
        "hr.appraisal.campaign.criterion", required=True, ondelete="cascade", index=True)
    level_id = fields.Many2one(
        "hr.appraisal.campaign.scale.level", "Level", required=True, ondelete="cascade")
    value = fields.Integer(related="level_id.value", store=True)
    level_name = fields.Char(related="level_id.name")
    description = fields.Text("Word Picture", translate=True,
                              help="What this level looks like for this criterion.")

    _level_unique = models.Constraint(
        "UNIQUE(criterion_id, level_id)", "A criterion has one word picture per level.")
