from odoo import fields, models

from .delivery_carrier import NMFC_FREIGHT_CLASSES


class ProductTemplate(models.Model):
    _inherit = "product.template"

    mycarrier_commodity_class = fields.Selection(
        NMFC_FREIGHT_CLASSES,
        string="MyCarrier NMFC Class",
        help="NMFC freight class used when booking this product via MyCarrier. "
        "Leave empty to use the default configured on the carrier.",
    )
    mycarrier_nmfc_code = fields.Char(
        string="MyCarrier NMFC Code",
        help="Optional NMFC item code (sub-class) used in MyCarrier commodity "
        "descriptions.",
    )
