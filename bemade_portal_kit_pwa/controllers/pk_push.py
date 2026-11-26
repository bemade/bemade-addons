# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5546 (pwa 1.2): the phone notification routes. ``auth='user'``,
404 while ``portal.kit._pk_push_available()`` is False (the kit's switch
off), not language-prefixed. POSTs check the CSRF token (http routes); the
service worker, which has no page, reads one from ``/my/app/push/key``.

* ``GET  /my/app/push/key[?endpoint=]``  ``{key, csrf_token, owner, registered}``
  (``registered``: ``mine`` / ``other`` / ``none`` for ``endpoint``)
* ``POST /my/app/push/register``  ``endpoint``, ``keys`` (JSON
  ``{p256dh, auth}``), ``expiration_time`` (ms), ``vapid_public_key``,
  ``previous_endpoint``, ``enable`` (``'1'``: an explicit « turn on »)
* ``POST /my/app/push/unregister``  ``endpoint`` (the caller's own only)
* ``POST /my/app/push/prompted``  the one-time prompt was answered
* ``GET  /my/app/push/badge``  ``{count}`` (the app icon's number)

The logout (``/web/session/logout``) removes the device this session
registered before the session ends (phones are shared in families).
"""
import json

import werkzeug.exceptions

from odoo import api, http
from odoo.http import request

from odoo.addons.web.controllers.session import Session

PK_PUSH_SESSION_KEY = 'pk_push_endpoint'


def _json(data, status=200):
    response = request.make_json_response(data, status=status)
    response.headers['Cache-Control'] = 'no-store'
    return response


def _logout_readonly(controller, rule, args):
    """Read-only, unless this session registered a phone to remove."""
    return not (request and request.session.get(PK_PUSH_SESSION_KEY))


class PortalKitPush(http.Controller):

    @staticmethod
    def _pk_push_guard():
        if not request.env['portal.kit']._pk_push_available():
            raise werkzeug.exceptions.NotFound()

    @http.route('/my/app/push/key', type='http', auth='user', methods=['GET'], multilang=False, sitemap=False)
    def pk_push_key(self, endpoint=None, **kw):
        self._pk_push_guard()
        kit = request.env['portal.kit']
        return _json({
            'key': kit._pk_push_public_key(),
            'csrf_token': request.csrf_token(),
            'owner': kit._pk_push_owner(),
            'registered': kit._pk_push_device_state(endpoint),
        })

    @http.route('/my/app/push/register', type='http', auth='user', methods=['POST'], multilang=False,
                sitemap=False)
    def pk_push_register(self, endpoint=None, keys=None, expiration_time=None, vapid_public_key=None,
                         previous_endpoint=None, enable=None, **kw):
        self._pk_push_guard()
        kit = request.env['portal.kit']
        try:
            keys = json.loads(keys or '')
        except ValueError:
            keys = None
        if not kit._pk_push_valid(endpoint, keys):
            return _json({'error': 'bad_request'}, 400)
        if not vapid_public_key or vapid_public_key != kit._pk_push_public_key():
            return _json({'error': 'invalid_key'}, 400)
        kinds = kit._pk_push_register(endpoint, keys, expiration_time=expiration_time,
                                      previous_endpoint=previous_endpoint, enable=enable == '1')
        request.session[PK_PUSH_SESSION_KEY] = endpoint
        return _json({'registered': True, 'owner': kit._pk_push_owner(), 'kinds_on': kinds})

    @http.route('/my/app/push/unregister', type='http', auth='user', methods=['POST'], multilang=False,
                sitemap=False)
    def pk_push_unregister(self, endpoint=None, **kw):
        self._pk_push_guard()
        removed = request.env['portal.kit']._pk_push_unregister(endpoint)
        if request.session.get(PK_PUSH_SESSION_KEY) == endpoint:
            request.session.pop(PK_PUSH_SESSION_KEY, None)
        return _json({'unregistered': removed})

    @http.route('/my/app/push/prompted', type='http', auth='user', methods=['POST'], multilang=False,
                sitemap=False)
    def pk_push_prompted(self, **kw):
        self._pk_push_guard()
        request.env.user.sudo().pk_push_prompted = True
        return _json({'prompted': True})

    @http.route('/my/app/push/badge', type='http', auth='user', methods=['GET'], multilang=False,
                sitemap=False, readonly=True)
    def pk_push_badge(self, **kw):
        self._pk_push_guard()
        return _json({'count': int(request.env['portal.kit']._pk_app_badge_count() or 0)})


class PortalKitPushSession(Session):

    @http.route(readonly=_logout_readonly)
    def logout(self, redirect='/odoo'):
        endpoint = request.session.get(PK_PUSH_SESSION_KEY)
        uid = request.session.uid
        if endpoint and uid:
            env = api.Environment(request.env.cr, uid, {})
            env['portal.kit']._pk_push_unregister(endpoint, user=env['res.users'].browse(uid))
            request.session.pop(PK_PUSH_SESSION_KEY, None)
        return super().logout(redirect=redirect)
