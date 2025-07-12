# -*- coding: utf-8 -*-
from odoo import models, fields, api


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'

    use_ai_sale_orders = fields.Boolean(
        string='Use AI for Sale Orders',
        help='If checked, the system will use AI to automatically generate sale orders from ticket descriptions.',
        default=False,
    )
    
    ai_prompt_template = fields.Text(
        string='AI Prompt Template',
        help='Template for the prompt sent to the AI. Use placeholders like {description}, {customer}, etc.',
        default="""Based on the following helpdesk ticket description, identify products and services that should be included in a sales order:

Ticket Description: {description}
Customer: {customer}

Please provide a list of products/services with quantities and descriptions in the following format:
Product/Service Name | Quantity | Description
"""
    )
