# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from urllib.parse import urlencode

from odoo import http
from odoo.http import request

from ..models.ir_http import CONSENT_PATH


class PortalConsent(http.Controller):

    @http.route([CONSENT_PATH], type='http', auth='user', website=True, methods=['GET'], sitemap=False)
    def portal_consent(self, redirect=None, **kw):
        """The pending documents, one at a time; none left: the target."""
        IrHttp = request.env['ir.http']
        target = IrHttp._portal_consent_safe_target(redirect)
        pending = request.env.user.sudo()._portal_consent_pending()
        if not pending:
            return request.redirect(IrHttp._portal_consent_url(target), code=303, local=True)
        document = pending[0].sudo()
        values = {
            'consent_document': document,
            'consent_version': document.current_version_id,
            'consent_redirect': target,
            'consent_total': len(pending),
            'no_breadcrumbs': True,
            'page_name': 'portal_consent',
        }
        return request.render('bemade_portal_consent.portal_consent_page', values)

    @http.route([CONSENT_PATH + '/accept'], type='http', auth='user', website=True, methods=['POST'],
                sitemap=False)
    def portal_consent_accept(self, version_id=None, redirect=None, **kw):
        """Log the acceptance of a pending document's current version, then
        back to the consent page (the next document, or the target)."""
        IrHttp = request.env['ir.http']
        target = IrHttp._portal_consent_safe_target(redirect)
        user = request.env.user
        try:
            version = request.env['portal.consent.version'].sudo().browse(int(version_id)).exists()
        except (TypeError, ValueError):
            version = None
        pending = user.sudo()._portal_consent_pending()
        if (version and version.state == 'published' and version.document_id.id in pending.ids
                and version == version.document_id.current_version_id):
            httprequest = request.httprequest
            version._portal_consent_accept(
                user, ip=httprequest.remote_addr, user_agent=httprequest.user_agent.string)
        url = IrHttp._portal_consent_url(CONSENT_PATH) + '?' + urlencode({'redirect': target})
        return request.redirect(url, code=303, local=True)
