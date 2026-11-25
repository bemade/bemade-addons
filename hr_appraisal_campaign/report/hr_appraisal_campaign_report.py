from odoo import api, models


class ReportCampaignAppraisal(models.AbstractModel):
    _name = "report.hr_appraisal_campaign.report_campaign_appraisal"
    _description = "Campaign Evaluation Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        return {
            "doc_ids": docids,
            "doc_model": "hr.appraisal",
            "docs": self.env["hr.appraisal"].browse(docids),
            "report_lang": data.get("report_lang") or self.env.lang or "en_US",
        }
