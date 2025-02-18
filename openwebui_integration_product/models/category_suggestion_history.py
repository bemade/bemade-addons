# -*- coding: utf-8 -*-

from odoo import models, fields

class CategorySuggestionHistory(models.Model):
    _name = 'product.category.suggestion.history'
    _description = 'Category Suggestion History'
    _order = 'create_date desc'

    product_id = fields.Many2one(
        comodel_name='product.template',
        string='Product',
        required=True,
        ondelete='cascade',
        help='Product for which the category was suggested'
    )

    suggested_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Suggested Category',
        required=True,
        help='Category suggested by AI analysis'
    )

    suggestion_confidence = fields.Float(
        string='Confidence Score',
        help='Confidence score of the suggestion (0-100)'
    )
    
    applied = fields.Boolean(
        string='Applied',
        help='Indicates if the suggestion was applied to the product'
    )
    
    suggestion_date = fields.Datetime(
        string='Suggestion Date',
        readonly=True,
        help='Date and time of the suggestion'
    )

    suggestion_uid = fields.Many2one(
        comodel_name='res.users',
        string='Created By',
        readonly=True,
        help='User who triggered the suggestion'
    )

    input_data = fields.Text(
        string='Analyzed Data',
        help='Data used by AI to generate the suggestion'
    )
    
    explanation = fields.Text(
        string='Explanation',
        help='Detailed explanation of category choice'
    )