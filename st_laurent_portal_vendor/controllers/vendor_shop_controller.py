from odoo import http
from odoo.http import request

class VendorShopController(http.Controller):
    @http.route(['/shop/<string:shop_slug>'], type='http', auth='public', website=True)
    def vendor_shop(self, shop_slug, **kwargs):
        # Extract the ID from the slug if it's in the format 'name-id'
        slug_parts = shop_slug.rsplit('-', 1)
        if len(slug_parts) == 2 and slug_parts[1].isdigit():
            shop_id = int(slug_parts[1])
            shop = request.env['vendor.shop'].sudo().browse(shop_id)
            if not shop.exists():
                shop = None
        else:
            # Fallback to searching by the full slug
            shop = request.env['vendor.shop'].sudo().search([('slug', '=', shop_slug)], limit=1)
        if not shop:
            return request.not_found()
        # Retrieve the products linked to the shop
        products = request.env['product.template'].sudo().search([
            ('vendor_shop_id', '=', shop.id),
            ('sale_ok', '=', True),
            ('website_published', '=', True),
        ])
        values = {
            'shop': shop,
            'products': products,
        }
        return request.render('st_laurent_portal_vendor.vendor_shop_page', values)
