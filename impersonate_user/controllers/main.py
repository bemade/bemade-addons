from odoo import http
from odoo.http import request


class UserImpersonationController(http.Controller):

    @http.route("/unimpersonate", type="json", auth="user")
    def unimpersonate(self):
        return request.env["res.users"].sudo().unimpersonate()
