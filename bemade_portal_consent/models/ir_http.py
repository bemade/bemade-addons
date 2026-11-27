# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
from urllib.parse import urlencode, urlsplit

import werkzeug.exceptions

from odoo import models
from odoo.http import request

CONSENT_PATH = '/my/consent'
DEFAULT_TARGET = '/my'
PREFIXES_PARAM = 'bemade_portal_consent.prefixes'
DEFAULT_PREFIXES = '/my'


def _under(path, prefix):
    prefix = prefix.rstrip('/') or '/'
    return prefix == '/' or path == prefix or path.startswith(prefix + '/')


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _pre_dispatch(cls, rule, args):
        result = super()._pre_dispatch(rule, args)
        cls._portal_consent_gate(rule)
        return result

    # ------------------------------------------------------------------
    # Helpers (also used by the consent page's controller)
    # ------------------------------------------------------------------
    @classmethod
    def _portal_consent_strip_lang(cls, path):
        """``path`` without a leading language URL code (``/fr/my`` ->
        ``/my``)."""
        parts = path.split('/', 2)
        if len(parts) > 1 and parts[1]:
            url_codes = {lang.url_code for lang in request.env['res.lang']._get_frontend().values()}
            if parts[1] in url_codes:
                return '/' + (parts[2] if len(parts) > 2 else '')
        return path

    @classmethod
    def _portal_consent_safe_target(cls, target):
        """``target`` when it is a relative path on this site (and not the
        consent page itself), else ``/my``: no open redirect."""
        if not target or not isinstance(target, str):
            return DEFAULT_TARGET
        target = target.strip()
        if (not target.startswith('/') or target.startswith('//') or '\\' in target
                or any(ord(char) < 32 for char in target)):
            return DEFAULT_TARGET
        parts = urlsplit(target)
        if parts.scheme or parts.netloc:
            return DEFAULT_TARGET
        if _under(cls._portal_consent_strip_lang(parts.path), CONSENT_PATH):
            return DEFAULT_TARGET
        return target

    @classmethod
    def _portal_consent_url(cls, path):
        """``path`` in the request's language (``/fr/...``) when the site
        is multilingual."""
        try:
            return request.env['ir.http']._url_lang(path)
        except Exception:  # noqa: BLE001 -- the plain path is always valid
            return path

    @classmethod
    def _portal_consent_prefixes(cls):
        value = request.env['ir.config_parameter'].sudo().get_param(PREFIXES_PARAM, DEFAULT_PREFIXES)
        return [prefix.strip() for prefix in (value or '').split(',') if prefix.strip().startswith('/')]

    @classmethod
    def _portal_consent_gated(cls, rule, path):
        """Whether the gate applies to this route and path (the user
        aside). Override to exempt more routes."""
        routing = rule.endpoint.routing
        if routing.get('type') != 'http' or routing.get('auth', 'user') != 'user':
            return False
        if _under(path, CONSENT_PATH):
            return False
        return any(_under(path, prefix) for prefix in cls._portal_consent_prefixes())

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    @classmethod
    def _portal_consent_gate(cls, rule):
        """A portal user with a pending consent document is sent (303) to
        the consent page, the original page kept in ``redirect``."""
        user = request.env.user
        if not user or not user.share or user._is_public():
            return
        path = cls._portal_consent_strip_lang(request.httprequest.path)
        if not cls._portal_consent_gated(rule, path):
            return
        if not user.sudo()._portal_consent_pending():
            return
        target = DEFAULT_TARGET
        if request.httprequest.method in ('GET', 'HEAD'):
            query = request.httprequest.query_string.decode()
            target = cls._portal_consent_safe_target(path + ('?' + query if query else ''))
        url = cls._portal_consent_url(CONSENT_PATH) + '?' + urlencode({'redirect': target})
        werkzeug.exceptions.abort(request.redirect(url, code=303, local=True))
