from odoo import http
from odoo.http import request

class VendorShopController(http.Controller):
    @http.route('/my/vendor/shop', type='http', auth='user', website=True)
    def vendor_shop(self, **kw):
        partner = request.env.user.partner_id
        products = partner.vendor_product_ids
        return request.render('st_laurent_vendor_orders.portal_vendor_shop_template', {
            'products': products,
        })