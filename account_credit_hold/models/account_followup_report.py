from odoo import models, fields, api, _


class FollowUpReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_followup_report_options(self, partner, options=None):
        """
        Override to include credit hold information in followup report options.
        """
        res = super()._get_followup_report_options(partner, options)
        res.update({
            'credit_hold': partner.followup_line_id.account_hold if partner.followup_line_id else False,
            'partner_on_hold': partner.on_hold
        })
        return res
