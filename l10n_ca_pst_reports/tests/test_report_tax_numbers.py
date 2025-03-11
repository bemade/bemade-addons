from odoo.tests import TransactionCase, tagged
from pdfminer.high_level import extract_text
import base64
import tempfile
import os

@tagged('post_install', '-at_install')
class TestReportTaxNumbers(TransactionCase):

    def setUp(self):
        super().setUp()
        # Create a Canadian company with GST and PST numbers
        self.company = self.env['res.company'].create({
            'name': 'Test Canadian Company',
            'country_id': self.env.ref('base.ca').id,
            'vat': '123456789',
            'l10n_ca_pst': 'PST12345',
        })
        self.env['account.chart.template'].try_loading('ca_2023', company=self.company)

        # Create a partner
        self.partner = self.env['res.partner'].create({
            'name': 'Test Customer',
            'country_id': self.env.ref('base.ca').id,
        })

        # Create an invoice to test with
        self.invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'company_id': self.company.id,
        })

    def _get_pdf_content(self, report_name, res_ids):
        """Generate PDF report and extract its text content."""
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_html(report_name, [res_ids])
        
        return str(pdf_content)

    def test_invoice_tax_numbers(self):
        """Test that GST and PST numbers appear on invoice report."""
        # Generate invoice PDF and extract text
        text = self._get_pdf_content('account.report_invoice', self.invoice.id)
        
        # Check for GST and PST numbers
        self.assertIn('GST: <span>123456789</span>', text, "GST number not found in invoice")
        self.assertIn('PST: <span>PST12345</span>', text, "PST number not found in invoice")

    def test_different_layouts(self):
        """Test tax numbers appear with different report layouts."""
        layouts = ['standard', 'boxed', 'bold', 'striped', 'bubble', 'wave', 'folder']
        
        for layout in layouts:
            # Set company layout
            layout_id = self.env.ref(f'web.external_layout_{layout}')
            self.company.write({'external_report_layout_id': layout_id.id})
            
            # Generate invoice PDF and extract text
            text = self._get_pdf_content('account.report_invoice', self.invoice.id)
            
            # Check for GST and PST numbers
            self.assertIn('GST: <span>123456789</span>', text, 
                         f"GST number not found in invoice with {layout} layout")
            self.assertIn('PST: <span>PST12345</span>', text, 
                         f"PST number not found in invoice with {layout} layout")