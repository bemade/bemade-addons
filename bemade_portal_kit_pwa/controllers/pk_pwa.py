# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): the installable app's routes (moved from the first
consumer, same URLs). Every public route answers 404 while the kit's switch
is off: the page script (``pk_sw_register.js``) then unregisters the worker
on every device (the kill switch). Stable URLs: ``multilang=False``.

Task 5391: ``/my/app.webmanifest``, the worker and the offline page are the
database's default app's (``portal.kit._pk_default_app()``; one worker per
site); ``/my/app/<app>.webmanifest`` is each app's manifest."""
import json

from markupsafe import Markup

from odoo import http
from odoo.http import request
from odoo.tools import file_open

from odoo.addons.bemade_portal_kit.controllers.pk_shell import PortalKitShell

from ..models.portal_kit import pk_pwa_style

PK_SW_SOURCE = 'bemade_portal_kit_pwa/static/src/sw/pk_service_worker.js'
_NO_CACHE = ('Cache-Control', 'no-cache')


class PortalKitPwa(PortalKitShell):

    @staticmethod
    def _pk_pwa_on():
        return request.env['portal.kit']._pk_shell_enabled()

    @http.route(['/my/app.webmanifest'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def pk_pwa_manifest(self, **kw):
        if not self._pk_pwa_on():
            raise request.not_found()
        kit = request.env['portal.kit']
        return self._pk_pwa_manifest_response(kit._pk_default_app())

    @http.route(['/my/app/<string:app>.webmanifest'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def pk_pwa_app_manifest(self, app, **kw):
        """Task 5391: the manifest of app ``app`` (404: unknown app)."""
        kit = request.env['portal.kit']
        if not self._pk_pwa_on() or app not in kit.pk_apps():
            raise request.not_found()
        return self._pk_pwa_manifest_response(app)

    @staticmethod
    def _pk_pwa_manifest_response(app):
        kit = request.env['portal.kit']
        manifest = kit._pk_pwa_manifest(kit._pk_pwa(app))
        return request.make_response(json.dumps(manifest), headers=[
            ('Content-Type', 'application/manifest+json'), _NO_CACHE])

    @http.route(['/my/service-worker.js'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def pk_pwa_service_worker(self, **kw):
        """The worker, allowed the whole origin (scope ``/``); ``no-cache`` so
        a device picks up a new version, or this route's 404, on its next
        visit."""
        if not self._pk_pwa_on():
            raise request.not_found()
        kit = request.env['portal.kit']
        pwa = kit._pk_pwa(kit._pk_default_app())
        with file_open(PK_SW_SOURCE) as source:
            body = source.read()
        body = (body
                .replace('__PK_SW_VERSION__', kit._pk_pwa_sw_version(pwa))
                .replace('"__PK_SW_PRECACHE__"', json.dumps(kit._pk_pwa_precache(pwa))))
        return request.make_response(body, headers=[
            ('Content-Type', 'text/javascript; charset=utf-8'), _NO_CACHE,
            ('Service-Worker-Allowed', '/')])

    @http.route(['/my/app/offline'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def pk_pwa_offline(self, **kw):
        """The DATA-FREE page the worker shows when a navigation fails
        offline. No layout: no user, no session information, no CSRF token
        (it is cached on the device)."""
        if not self._pk_pwa_on():
            raise request.not_found()
        kit = request.env['portal.kit']
        pwa = kit._pk_pwa(kit._pk_default_app())
        # The doctype is prepended here: a raw text node at the template
        # root changes how the view's terms are extracted.
        html = request.env['ir.ui.view']._render_template('bemade_portal_kit_pwa.pk_app_offline', {
            'pk_pwa': pwa,
            'pk_offline_style': pk_pwa_style(kit._pk_pwa_offline_style(pwa)),
        })
        return request.make_response(Markup('<!DOCTYPE html>\n') + html,
                                     headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route(['/my/app/icon/<string:name>'], type='http', auth='public', methods=['GET'],
                multilang=False, sitemap=False)
    def pk_pwa_icon(self, name, **kw):
        if not self._pk_pwa_on():
            raise request.not_found()
        icon = request.env['portal.kit']._pk_pwa_icon(name)
        if not icon:
            raise request.not_found()
        data, mimetype = icon
        return request.make_response(data, headers=[
            ('Content-Type', mimetype), _NO_CACHE, ('X-Content-Type-Options', 'nosniff')])

    @http.route(['/my/app/install'], type='http', auth='user', website=True, multilang=False)
    def pk_pwa_install(self, **kw):
        """« More › Install the app »: the per-device steps. No banner
        anywhere else."""
        if not self._pk_shell_active():
            return request.redirect('/my/home')
        values = self._prepare_portal_layout_values()
        values['pk_pwa'] = request.env['portal.kit']._pk_pwa()
        return self._pk_page('bemade_portal_kit_pwa.pk_app_install', values)
