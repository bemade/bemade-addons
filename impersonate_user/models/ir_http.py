from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        result["user_impersonated"] = bool(request.session.get("original_uid", False))
        return result
