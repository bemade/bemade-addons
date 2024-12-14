from odoo import models, fields, api, _
from odoo.exceptions import UserError
from openai import OpenAI
from datetime import datetime
from bs4 import BeautifulSoup
from markupsafe import escape

# Import conditionnel de queue_job pour gérer les files d'attente si elles sont disponibles
try:
    from odoo.addons.queue_job.job import job
except ImportError:
    job = None  # Si queue_job n'est pas disponible, job reste None

class PartnerPurchaseAnalysisWizard(models.TransientModel):
    _name = 'partner.purchase.analysis.wizard'
    _description = 'Wizard for Partner Purchase Analysis with OpenAI'

    partner_id = fields.Many2one('res.partner', string="Customer", required=True, readonly=True)
    date_start = fields.Date(string="Start Date", required=True)
    date_end = fields.Date(string="End Date", default=fields.Date.today, required=True)

    def start_analysis(self):
        """Lance l'analyse en arrière-plan si `queue_job` est disponible, sinon exécute immédiatement."""
        use_queue = self.env['ir.config_parameter'].sudo().get_param('my_module.use_queue_job')
        if use_queue and job:
            return self.with_delay().perform_analysis()
        else:
            return self.perform_analysis()

    def perform_analysis(self):
        """Effectue l'analyse des ventes pour le partenaire sélectionné."""

        # Récupération de l'organisation et de la clé API OpenAI dans les paramètres
        organization = self.env['ir.config_parameter'].sudo().get_param('openai_connector.organization')
        api_key = self.env['ir.config_parameter'].sudo().get_param('openai_connector.api_key')

        if not api_key or not organization:
            raise UserError(_("API Key or Organization ID for OpenAI is missing in settings."))

        client = OpenAI(
            api_key=api_key,
            organization=organization
        )

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

        domain.append(('order_id.state', 'in', ['sale', 'done']))

        sale_order_lines = self.env['sale.order.line'].search(domain)

        if not sale_order_lines:
            raise UserError(_("No relevant purchase history found for this customer based on the selected filters."))

        # Préparation des données pour le prompt OpenAI
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

        # Prompt défini en plusieurs lignes pour lisibilité
        user_lang = self.env.user.lang or 'en_US'
        user_lang_name = self.env['res.lang'].search([('code', '=', user_lang)], limit=1).name or "English"

        prompt = (
            "Analyze all the sale order lines of the following customer. Identify trends, "
            "and any significant deviations. Respond in "
            f"{user_lang_name}.  Produce the analysis adding next plan purchase or lost purchase.  You output all "
            "in html format.  Focus on missing product order and deviation from the average. "
            "Be sure to list all products and categories in the analysis.  Try to identify "
            "the next purchase date for all product and warn if the customer is not buying "
            "and identify recurring sale and product not sale.  Put in the analysis if the product is not bought "
            "in the last 12 months and show those product as lost sale with a value of the lost sales"
        )

        # Construction de `purchase_details` pour le contenu du prompt
        purchase_details = f"Customer Purchase Analysis Grouped by Product Category and Product:\n\n"
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

        # Appel à l'API OpenAI
        try:
            response = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": purchase_details
                    }
                ],
                model="gpt-4o",
            )

            # Supposons que `response` contient la réponse complète au format HTML
            response_text = response.choices[0].message.content

            # Parse avec BeautifulSoup pour extraire le contenu du <body>
            soup = BeautifulSoup(response_text, "html.parser")
            body_content = soup.body

            # Si body est présent, on utilise son contenu ; sinon, on utilise tout le texte
            cleaned_text = escape(body_content.get_text()) if body_content else escape(response_text)

            # Ajouter des balises de base pour structurer le texte en HTML simple
            html_content = f"<div>{cleaned_text.replace('\n', '<br/>')}</div>"

            self.partner_id.sale_analysis = body_content
            self.partner_id.sale_analysis_date = fields.Datetime.today()
#            self.sale_analysis = response.choices[0].message.content
#            self.sale_analysis_date =  fields.Datetime.today()
            print(response.choices[0].message.content)
        except Exception as e:
            raise UserError(_("Failed to get response from OpenAI. Error: %s") % str(e))