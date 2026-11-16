# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): the installable app's resolver and hooks on
``portal.kit``.

* ``_pk_pwa(app=None)``: the effective installable app of ``app`` (default:
  the viewer's app; company fields, else the brand's defaults and the
  kit's neutral icons); never cached (per company);
* hooks ``_pk_pwa_start_url(app)``, ``_pk_pwa_manifest_id(app)``,
  ``_pk_pwa_shortcuts(app)``, ``_pk_pwa_offline_style(pwa)``: by default
  they read the app's ``pwa`` registration (``portal.kit._pk_apps()``,
  task 5391);
* task 5391: ``/my/app.webmanifest`` is the database's default app
  (``_pk_default_app()``), ``/my/app/<app>.webmanifest`` each app's
  (``_pk_pwa_manifest_url(app)``); the service worker and the offline page
  are the default app's (one worker per site);
* ``_pk_pwa_manifest()``, ``_pk_pwa_icon(name)``, ``_pk_pwa_precache()``,
  ``_pk_pwa_sw_version()``;
* the « More » entry ``install`` and the page ``pk_app_install``.
"""
import base64
import hashlib
import json
import re

from odoo import api, models
from odoo.modules.module import get_manifest
from odoo.tools import file_open
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.translate import LazyTranslate

from odoo.addons.bemade_portal_kit.tools import pk_nav, pk_static_page

_lt = LazyTranslate(__name__)

PWA = 'bemade_portal_kit_pwa'
PK_PWA_OFFLINE_URL = '/my/app/offline'
PK_PWA_INSTALL_URL = '/my/app/install'
PK_PWA_MANIFEST_URL = '/my/app.webmanifest'
PK_PWA_APP_MANIFEST_URL = '/my/app/%s.webmanifest'
PK_PWA_ICON_URL = '/my/app/icon/'
PK_PWA_OFFLINE_CSS = '/bemade_portal_kit_pwa/static/src/css/pk_offline.css'
_DEFAULT_IMG = 'bemade_portal_kit_pwa/static/src/img/'
# (URL name, company field, the kit's default file, manifest sizes, manifest
# purpose — None: not in the manifest)
PK_PWA_ICONS = (
    ('icon-192.png', 'pk_pwa_icon_192', 'pk_icon_192.png', '192x192', 'any'),
    ('icon-512.png', 'pk_pwa_icon_512', 'pk_icon_512.png', '512x512', 'any'),
    ('icon-maskable-512.png', 'pk_pwa_icon_maskable_512', 'pk_icon_maskable_512.png', '512x512', 'maskable'),
    ('apple-touch-icon.png', 'pk_pwa_apple_touch_icon', 'pk_apple_touch_icon.png', '180x180', None),
    ('logo.png', 'pk_pwa_logo', 'pk_logo.png', '192x192', None),
)
PK_PWA_FIELDS = ('pk_pwa_name', 'pk_pwa_short_name', 'pk_pwa_background_color', 'pk_pwa_theme_color') + tuple(
    icon[1] for icon in PK_PWA_ICONS)
PK_PWA_ICON_TYPES = ('image/png', 'image/jpeg', 'image/webp', 'image/gif')
_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')
_STYLE_KEY_RE = re.compile(r'^[a-z][a-z-]*$')
_STYLE_BAD = re.compile(r'[;{}<>\\]')


def pk_pwa_color(value):
    """``value`` if it is a ``#rgb`` / ``#rrggbb`` colour, else None."""
    value = (value or '').strip()
    return value if _COLOR_RE.match(value) else None


def pk_pwa_is_dark(color):
    """Is ``#rrggbb`` dark (relative luminance under 0.4)?"""
    value = color.lstrip('#')
    if len(value) == 3:
        value = ''.join(ch * 2 for ch in value)
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.4


def pk_pwa_style(style):
    """``{key: value}`` -> the inline ``--pk-offline-<key>: value`` list
    (a key or value that could leave the declaration is dropped)."""
    return '; '.join(
        '--pk-offline-%s: %s' % (key, value) for key, value in style.items()
        if value and _STYLE_KEY_RE.match(key) and not _STYLE_BAD.search(str(value)))


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    # ------------------------------------------------------------------
    # Registries: the « More » entry and the page
    # ------------------------------------------------------------------
    @api.model
    def _pk_nav(self):
        # Every app role (an entry declares its roles; the app roles are the
        # roles registry's, built before the nav).
        return super()._pk_nav() + [
            pk_nav('install', _lt('Install the app'), 'install', PK_PWA_INSTALL_URL, self.pk_app_roles(), 160,
                   ('plus',), subtitle=_lt('Add the app to your home screen')),
        ]

    @api.model
    def _pk_pages(self):
        return super()._pk_pages() + [
            pk_static_page('pk_app_install', PK_PWA_INSTALL_URL, _lt('Install the app'),
                           parent=lambda v: ('pk_app_more', {})),
        ]

    @api.model
    def _pk_help_keys(self):
        keys = dict(super()._pk_help_keys())
        keys['pk_app_install'] = 'install'
        return keys

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    @api.model
    def _pk_pwa_spec(self, app=None):
        """The ``pwa`` registration of ``app`` (``_pk_apps()``), or ``{}``."""
        return self.pk_app_spec(app).get('pwa') or {}

    @api.model
    def _pk_pwa_start_url(self, app=None):
        """The installed app's start URL: the app's ``pwa.start_url``, else
        the brand's home."""
        return (self._pk_pwa_spec(app).get('start_url')
                or self.pk_brand(app=app).get('home_url') or '/my')

    @api.model
    def _pk_pwa_manifest_id(self, app=None):
        """The manifest ``id``: the app's ``pwa.manifest_id``, else the start
        URL. Never change it on a live app: an installed app with another id
        is a second app (two apps of one database: give each its own)."""
        return self._pk_pwa_spec(app).get('manifest_id') or self._pk_pwa_start_url(app)

    @api.model
    def _pk_pwa_shortcuts(self, app=None):
        """``[{'name': str, 'url': str}]``: the app icon's shortcuts, the
        app's ``pwa.shortcuts`` (a list, or ``callable(kit)``); default:
        none."""
        shortcuts = self._pk_pwa_spec(app).get('shortcuts') or []
        if callable(shortcuts):
            shortcuts = shortcuts(self)
        return [{'name': str(item['name']), 'url': item['url']} for item in shortcuts or []]

    @api.model
    def _pk_pwa_manifest_url(self, app=None):
        """The manifest URL of ``app`` (default: the viewer's app): the
        public ``/my/app.webmanifest`` for the default app (an installed
        app keeps its URL), else ``/my/app/<app>.webmanifest``."""
        app = self._pk_resolve_app(app)
        if not app or app == self._pk_default_app():
            return PK_PWA_MANIFEST_URL
        return PK_PWA_APP_MANIFEST_URL % app

    @api.model
    def _pk_pwa_offline_style(self, pwa):
        """The offline page's colours and fonts (``--pk-offline-<key>``):
        bg, fg, muted, accent, accent-fg, font, title-font,
        title-transform, title-spacing. Default: the background colour and
        readable neutral text, the kit's accent; the system fonts. The
        app's ``pwa.offline_style`` (a dict, or ``callable(kit, pwa)``) is
        merged over it."""
        bg = pwa['background_color']
        dark = pk_pwa_is_dark(bg)
        style = {
            'bg': bg,
            'fg': '#f8fafc' if dark else '#0f172a',
            'muted': '#94a3b8' if dark else '#475569',
            'accent': '#3b82f6' if dark else '#2563eb',
            'accent-fg': '#ffffff',
        }
        own = self._pk_pwa_spec(pwa.get('app')).get('offline_style')
        if callable(own):
            own = own(self, pwa)
        style.update(own or {})
        return style

    # ------------------------------------------------------------------
    # Resolver
    # ------------------------------------------------------------------
    @api.model
    def _pk_pwa(self, app=None):
        """The effective installable app ``app`` (default: the viewer's app)
        of the current company: ``{app, name, short_name, background_color,
        theme_color, start_url, id, scope, display, shortcuts, icons: {url
        name: url}, offline_url, install_url, manifest_url}``."""
        app = self._pk_resolve_app(app)
        company = self.env.company.sudo()
        brand = self.pk_brand(app=app)
        name = (company.pk_pwa_name or '').strip() or brand.get('name') or ''
        short_name = (company.pk_pwa_short_name or '').strip() or name
        light = pk_pwa_color((brand.get('theme_colors') or {}).get('light')) or '#ffffff'
        background = pk_pwa_color(company.pk_pwa_background_color) or light
        theme = pk_pwa_color(company.pk_pwa_theme_color) or background
        start_url = self._pk_pwa_start_url(app)
        return {
            'app': app or False,
            'name': name,
            'short_name': short_name,
            'background_color': background,
            'theme_color': theme,
            'start_url': start_url,
            'id': self._pk_pwa_manifest_id(app) or start_url,
            'scope': '/',
            'display': 'standalone',
            'shortcuts': [dict(shortcut) for shortcut in self._pk_pwa_shortcuts(app)],
            'icons': {icon[0]: PK_PWA_ICON_URL + icon[0] for icon in PK_PWA_ICONS},
            'offline_url': PK_PWA_OFFLINE_URL,
            'install_url': PK_PWA_INSTALL_URL,
            'manifest_url': self._pk_pwa_manifest_url(app),
        }

    @api.model
    def _pk_pwa_manifest(self, pwa=None):
        """The web manifest (a dict, in the keys' usual order)."""
        pwa = pwa or self._pk_pwa()
        manifest = {key: pwa[key] for key in (
            'name', 'short_name', 'id', 'start_url', 'scope', 'display', 'background_color', 'theme_color')}
        manifest['icons'] = [
            {'src': pwa['icons'][name], 'sizes': sizes, 'type': self._pk_pwa_icon(name)[1], 'purpose': purpose}
            for name, _field, _default, sizes, purpose in PK_PWA_ICONS if purpose]
        if pwa['shortcuts']:
            manifest['shortcuts'] = pwa['shortcuts']
        return manifest

    @api.model
    def _pk_pwa_icon(self, name):
        """``(bytes, mimetype)`` of icon ``name`` (``PK_PWA_ICONS``): the
        company's field as uploaded, else the kit's neutral icon. None for an
        unknown name."""
        for icon_name, field, default, _sizes, _purpose in PK_PWA_ICONS:
            if icon_name == name:
                value = self.env.company.sudo()[field]
                if value:
                    data = base64.b64decode(value)
                    mimetype = guess_mimetype(data, default='')
                    # Raster images only: an uploaded SVG / HTML is never
                    # served from this origin.
                    if mimetype in PK_PWA_ICON_TYPES:
                        return data, mimetype
                with file_open(_DEFAULT_IMG + default, 'rb') as source:
                    return source.read(), 'image/png'
        return None

    @api.model
    def _pk_pwa_precache(self, pwa=None):
        """What the service worker precaches besides the offline page: URLs
        that always answer 200 (an install whose precache fails keeps the
        old worker). Never a page with data."""
        pwa = pwa or self._pk_pwa()
        return [PK_PWA_OFFLINE_CSS, pwa['icons']['logo.png'], pwa['icons']['icon-192.png']]

    @api.model
    def _pk_pwa_sw_version(self, pwa=None):
        """The service worker's version: this addon's and the kit's versions
        + a hash of the effective branding (names, colours, offline style,
        precache list, icon contents). Any of them changing installs a new
        worker, which re-precaches and drops the older caches."""
        pwa = pwa or self._pk_pwa()
        company = self.env.company.sudo()
        attachments = self.env['ir.attachment'].sudo().search_read([
            ('res_model', '=', 'res.company'), ('res_id', '=', company.id),
            ('res_field', 'in', [icon[1] for icon in PK_PWA_ICONS])], ['res_field', 'checksum'])
        checksums = sorted((att['res_field'], att['checksum'] or '') for att in attachments)
        branding = {
            # Task 5391: the app key and manifest URL are not branding.
            'pwa': {key: value for key, value in pwa.items()
                    if key not in ('shortcuts', 'app', 'manifest_url')},
            'style': self._pk_pwa_offline_style(pwa),
            'precache': self._pk_pwa_precache(pwa),
            'icons': checksums,
        }
        digest = hashlib.sha1(json.dumps(branding, sort_keys=True, default=str).encode()).hexdigest()[:10]
        return '%s-%s-%s' % (
            get_manifest(PWA).get('version') or '0',
            get_manifest('bemade_portal_kit').get('version') or '0',
            digest)
