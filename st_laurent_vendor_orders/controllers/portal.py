# -*- coding: utf-8 -*-

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.osv.expression import OR


class VendorOrderPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        vendor_order_model = request.env['vendor.order']
        if 'vendor_order_count' in counters:
            values['vendor_order_count'] = vendor_order_model.search_count([
                ('vendor_id', '=', partner.id)
            ]) if vendor_order_model.check_access_rights('read', raise_exception=False) else 0

        return values

    def _get_vendor_order_domain(self, partner):
        return [
            ('vendor_id', '=', partner.id),
        ]

    @http.route(['/my/vendor/orders', '/my/vendor/orders/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_vendor_orders(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        values = self._prepare_portal_layout_values()
        partner = request.env.user.partner_id
        VendorOrder = request.env['vendor.order']

        domain = self._get_vendor_order_domain(partner)

        if date_begin and date_end:
            domain += [('date_order', '>', date_begin), ('date_order', '<=', date_end)]

        searchbar_sortings = {
            'date': {'label': _('Date de commande'), 'order': 'date_order desc'},
            'name': {'label': _('Référence'), 'order': 'name'},
            'state': {'label': _('Statut'), 'order': 'state'},
        }

        searchbar_filters = {
            'all': {'label': _('Toutes'), 'domain': []},
            'new': {'label': _('Nouvelles'), 'domain': [('state', '=', 'new')]},
            'processing': {'label': _('En traitement'), 'domain': [('state', '=', 'processing')]},
            'shipped': {'label': _('Expédiées'), 'domain': [('state', '=', 'shipped')]},
            'delivered': {'label': _('Livrées'), 'domain': [('state', '=', 'delivered')]},
            'cancelled': {'label': _('Annulées'), 'domain': [('state', '=', 'cancelled')]},
        }

        # default sortby order
        if not sortby:
            sortby = 'date'
        sort_order = searchbar_sortings[sortby]['order']

        # default filter by value
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']

        # count for pager
        vendor_order_count = VendorOrder.search_count(domain)

        # make pager
        pager = portal_pager(
            url="/my/vendor/orders",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=vendor_order_count,
            page=page,
            step=self._items_per_page
        )

        # search the count to display, according to the pager data
        vendor_orders = VendorOrder.search(domain, order=sort_order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_vendor_orders_history'] = vendor_orders.ids[:100]

        values.update({
            'date': date_begin,
            'vendor_orders': vendor_orders,
            'page_name': 'vendor_order',
            'pager': pager,
            'default_url': '/my/vendor/orders',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
        })
        return request.render("st_laurent_vendor_orders.portal_my_vendor_orders", values)

    @http.route(['/my/vendor/orders/<int:order_id>'], type='http', auth="user", website=True)
    def portal_my_vendor_order_detail(self, order_id, **kw):
        try:
            order_sudo = self._document_check_access('vendor.order', order_id)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = self._vendor_order_get_page_view_values(order_sudo, **kw)
        return request.render("st_laurent_vendor_orders.portal_vendor_order_page", values)

    def _vendor_order_get_page_view_values(self, order, **kwargs):
        values = {
            'order': order,
            'page_name': 'vendor_order',
        }
        return self._get_page_view_values(order, False, values, 'my_vendor_orders_history', False, **kwargs)

    @http.route(['/my/vendor/orders/<int:order_id>/ship'], type='http', auth="user", website=True)
    def portal_vendor_order_ship(self, order_id, tracking_number=None, carrier_id=None, **kw):
        try:
            order_sudo = self._document_check_access('vendor.order', order_id)
        except (AccessError, MissingError):
            return request.redirect('/my')

        if tracking_number and carrier_id:
            order_sudo.write({
                'tracking_number': tracking_number,
                'carrier_id': int(carrier_id),
            })
            order_sudo.action_ship()
            return request.redirect('/my/vendor/orders/%s' % order_id)

        carriers = request.env['delivery.carrier'].sudo().search([])
        values = {
            'order': order_sudo,
            'carriers': carriers,
            'page_name': 'vendor_order',
        }
        return request.render("st_laurent_vendor_orders.portal_vendor_order_ship", values)
