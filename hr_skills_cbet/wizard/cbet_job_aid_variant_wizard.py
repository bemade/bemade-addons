from odoo import api, fields, models


class CbetJobAidVariantWizard(models.TransientModel):
    """UC-CAT-08 — "Duplicate as variant": copy a job aid (sections and lines)
    under a new equipment variant of the same competency. A plain Duplicate
    would trip the one-card-per-variant rule."""

    _name = "cbet.job.aid.variant.wizard"
    _description = "Duplicate a job aid as a variant"

    job_aid_id = fields.Many2one(
        "cbet.job.aid", string="Job aid", required=True, ondelete="cascade",
    )
    competency_id = fields.Many2one(related="job_aid_id.competency_id")
    variant = fields.Char(
        required=True,
        help="Equipment family the new card is specific to (e.g. RO).",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if not res.get("job_aid_id") and ctx.get("active_model") == "cbet.job.aid":
            res["job_aid_id"] = ctx.get("active_id")
        return res

    def action_duplicate(self):
        self.ensure_one()
        new = self.job_aid_id.copy({"variant": self.variant.strip()})
        return {
            "type": "ir.actions.act_window",
            "name": new.name,
            "res_model": "cbet.job.aid",
            "res_id": new.id,
            "view_mode": "form",
            "target": "current",
        }
