from odoo import models, fields, api, _
from odoo.exceptions import UserError
import openai

try:
    from odoo.addons.queue_job.job import job
except ImportError:
    job = None  # Si queue_job n'est pas disponible, job reste None


class PartnerPurchaseAnalysisWizard(models.TransientModel):
    _name = 'partner.purchase.analysis.wizard'
    _description = 'Wizard for Partner Purchase Analysis with OpenAI'

    partner_id = fields.Many2one('res.partner', string="Customer", required=True, readonly=True)
    date_start = fields.Date(string="Start Date")
    date_end = fields.Date(string="End Date")
    analysis_result = fields.Text(string="Analysis Result", readonly=True)

    def start_analysis(self):
        use_queue = self.env['ir.config_parameter'].sudo().get_param('my_module.use_queue_job')
        if use_queue and job:
            return self.with_delay().perform_analysis()
        else:
            return self.perform_analysis()

    def perform_analysis(self):
        """Effectue l'analyse des ventes pour le partenaire sélectionné."""
        selected_categories = self.env.company.product_categories_analyzed
        if selected_categories:
            category_ids = selected_categories.ids
            domain = [
                ('order_id.partner_id', '=', self.partner_id.id),
                ('product_id.categ_id', 'child_of', category_ids),
            ]
        else:
            domain = [('order_id.partner_id', '=', self.partner_id.id)]

        if self.date_start:
            domain.append(('order_id.date_order', '>=', self.date_start))
        if self.date_end:
            domain.append(('order_id.date_order', '<=', self.date_end))

        sale_order_lines = self.env['sale.order.line'].search(domain)

        if not sale_order_lines:
            raise UserError(_("No relevant purchase history found for this customer based on the selected filters."))

        # Préparation des données pour l'API d'OpenAI
        purchase_data = {}
        for line in sale_order_lines:
            category_name = line.product_id.categ_id.name or "Uncategorized"
            if category_name not in purchase_data:
                purchase_data[category_name] = {}
            product_name = line.product_id.display_name
            if product_name not in purchase_data[category_name]:
                purchase_data[category_name][product_name] = []
            purchase_data[category_name][product_name].append({
                'date': line.order_id.date_order,
                'quantity': line.product_uom_qty,
                'unit_price': line.price_unit,
            })

        # Construire le prompt pour OpenAI
        user_lang = self.env.user.lang or 'en_US'
        user_lang_name = self.env['res.lang'].search([('code', '=', user_lang)], limit=1).name or "English"

        purchase_details = f"Customer Purchase Analysis Grouped by Product Category and Product (Response in {user_lang_name}):\n\n"
        for category, products in purchase_data.items():
            purchase_details += f"Category: {category}\n"
            for product, entries in products.items():
                purchase_details += f"  Product: {product}\n"
                for entry in entries:
                    purchase_details += (
                        f"    - Date: {entry['date']}, "
                        f"Qty: {entry['quantity']}, "
                        f"U.Price: {entry['unit_price']}\n"
                    )
                purchase_details += "\n"
            purchase_details += "\n"

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system",
                     "content": f"Analyze the following customer purchase history. Identify trends, product category preferences, and any significant deviations. Respond in {user_lang_name}."},
                    {"role": "user", "content": purchase_details}
                ]
            )
            self.analysis_result = response.choices[0].message['content']
        except Exception as e:
            raise UserError(_("Failed to get response from OpenAI. Error: %s") % str(e))