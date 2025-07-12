# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # Utiliser un champ calculé au lieu d'un champ simple avec onchange
    team_use_ai_sale_orders = fields.Boolean(
        string='Team Uses AI for Sale Orders',
        compute='_compute_team_use_ai_sale_orders',
    )
    
    @api.depends('team_id')
    def _compute_team_use_ai_sale_orders(self):
        for ticket in self:
            ticket.team_use_ai_sale_orders = False
            if ticket.team_id:
                # Vérifier si le champ existe sur l'équipe
                team = self.env['helpdesk.team'].sudo().browse(ticket.team_id.id)
                if hasattr(team, 'use_ai_sale_orders'):
                    ticket.team_use_ai_sale_orders = team.use_ai_sale_orders
    
    ai_generated_products = fields.Text(
        string='AI Generated Products',
        readonly=True,
        help='Products suggested by AI based on ticket description',
    )
    
    def action_convert_to_sale_order(self):
        """Override to use AI for generating sale order if enabled"""
        self.ensure_one()
        
        # Check if the team allows sale orders
        if not self.team_use_sale_orders:
            raise UserError(_("You cannot create a sale order from this ticket because your team does not allow it."))
        
        # Vérifier directement sur l'équipe si l'IA est activée
        use_ai = False
        if self.team_id and hasattr(self.team_id, 'use_ai_sale_orders'):
            use_ai = self.team_id.use_ai_sale_orders
        
        # If AI is enabled for this team, use it to generate the sale order
        if use_ai:
            return self._ai_convert_to_sale_order()
        
        # Otherwise, use the standard method from the parent module
        return super(HelpdeskTicket, self).action_convert_to_sale_order()
    
    def _ai_convert_to_sale_order(self):
        """Create a sale order using AI to suggest products based on ticket description"""
        self.ensure_one()
        
        # Generate AI suggestions if not already done
        if not self.ai_generated_products:
            self._generate_ai_product_suggestions()
        
        # Create the sale order with AI-suggested products
        so_vals = self._generate_ai_so_values()
        sale_order = self.env['sale.order'].create([so_vals])
        
        # Link the sale order to the ticket
        self.write({
            'sale_order_id': sale_order.id,
        })
        
        # Return the action to view the created sale order
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'context': {'create': False},
        }
    
    def _generate_ai_product_suggestions(self):
        """Use AI to generate product suggestions based on ticket description"""
        self.ensure_one()
        
        # Skip if no description
        if not self.description:
            return False
        
        try:
            # Prepare the prompt using the template from the team
            prompt = self.team_id.ai_prompt_template.format(
                description=self.description,
                customer=self.partner_id.name or 'Unknown',
            )
            
            # Call the AI service (assuming an OpenAI connector module exists)
            ai_service = self.env['openai.service'].sudo()
            response = ai_service.generate_completion(prompt)
            
            # Store the AI response
            self.ai_generated_products = response
            
            return True
        except Exception as e:
            _logger.error("Error generating AI product suggestions: %s", str(e))
            return False
    
    def _generate_ai_so_values(self):
        """Generate sale order values with AI-suggested products"""
        # Start with the base SO values from the parent method
        so_vals = self._generate_so_values()
        
        # Parse AI suggestions and add as order lines
        if self.ai_generated_products:
            order_lines = self._parse_ai_product_suggestions()
            if order_lines:
                so_vals['order_line'] = order_lines
        
        return so_vals
    
    def _parse_ai_product_suggestions(self):
        """Parse the AI-generated product suggestions into sale order lines"""
        order_lines = []
        
        if not self.ai_generated_products:
            return order_lines
        
        # Simple parsing of the AI response
        # Format expected: Product/Service Name | Quantity | Description
        lines = self.ai_generated_products.strip().split('\n')
        
        for line in lines:
            if '|' not in line:
                continue
                
            parts = [part.strip() for part in line.split('|')]
            if len(parts) < 2:
                continue
                
            product_name = parts[0]
            quantity = 1.0
            description = ''
            
            # Try to parse quantity
            if len(parts) > 1:
                try:
                    quantity = float(parts[1])
                except ValueError:
                    quantity = 1.0
            
            # Get description if available
            if len(parts) > 2:
                description = parts[2]
            
            # Search for matching product
            product = self.env['product.product'].search([
                ('name', 'ilike', product_name),
                ('sale_ok', '=', True)
            ], limit=1)
            
            if not product:
                # If no product found, create a service product
                product = self.env['product.product'].create({
                    'name': product_name,
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'list_price': 0.0,
                })
            
            # Create order line
            order_line = (0, 0, {
                'product_id': product.id,
                'product_uom_qty': quantity,
                'name': description or product.name,
            })
            
            order_lines.append(order_line)
        
        return order_lines
