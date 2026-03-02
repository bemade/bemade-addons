from odoo import models, fields, api, _
from odoo.tools import float_is_zero


class FollowUpReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_line_info(self, followup_line):
        res = super()._get_line_info(followup_line)
        res.update({
            'credit_hold': followup_line.account_hold
        })
        return res

    def _generate_credit_hold_attachment(self, partner):
        """
        Generate PDF attachment for credit hold customers to be sent with followup emails.
        """
        if not partner.on_hold:
            return None
            
        # Generate the PDF report
        report = self.env.ref('account_credit_hold.account_credit_hold_report_action')
        pdf_content, _ = report._render_qweb_pdf([partner.id])
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Credit_Hold_Report_{partner.name.replace(" ", "_")}.pdf',
            'type': 'binary',
            'datas': pdf_content,
            'res_model': 'res.partner',
            'res_id': partner.id,
            'description': f'Credit hold report for {partner.name}'
        })
        
        return attachment

    def _send_email(self, options):
        """
        Override to include credit hold report as attachment for customers on hold.
        PDF is sent with EVERY followup email when customer is on credit hold.
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        
        # Generate credit hold attachment for ANY customer on credit hold (no configuration needed)
        if partner.on_hold:
            attachment = self._generate_credit_hold_attachment(partner)
            if attachment:
                # Add attachment to options
                attachment_ids = options.get('attachment_ids', [])
                attachment_ids.append((4, attachment.id))
                options['attachment_ids'] = attachment_ids
        
        # Call the original method
        return super()._send_email(options)

    def _get_main_body(self, options):
        """
        Override to add credit hold information to email body.
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        body = super()._get_main_body(options)
        
        # Add credit hold notice if partner is on hold
        if partner.on_hold:
            credit_hold_notice = _(
                "<div style='background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0; border-radius: 4px;'>"
                "<strong style='color: #856404;'>⚠️ Credit Hold Notice:</strong> "
                "Your account is currently on credit hold due to overdue invoices. "
                "Please settle the outstanding amounts to avoid service interruptions. "
                "Total amount due: <strong>%s</strong>"
                "</div>",
                partner.total_due
            )
            body = credit_hold_notice + body
        
        return body
