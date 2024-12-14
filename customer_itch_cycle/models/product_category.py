
from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = 'product.category'

    seasonal_factor = fields.Boolean(
        string="Catégorie saisonnière",
        default=False
    )

    season_months = fields.Char(
        string="Mois actifs",
        help="Mois pendant lesquels cette catégorie est active (ex: '3,4,5' pour mars-mai)"
    )
