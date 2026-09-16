from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        # Serve this module's _t() strings (portal_sale.js toasts) to the website
        # frontend; only modules listed here get their JS translations bundled.
        return super()._get_translation_frontend_modules_name() + [
            "sale_mandatory_customer_reference"
        ]
