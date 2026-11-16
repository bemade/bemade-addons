# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): the installable app, with this addon alone (no
consumer's hooks). Synthetic users and images only.

Acceptance criteria:

* UC-W1 Switch off: the manifest, the worker, the offline page and the
  icons answer 404; the install page redirects home.
* UC-W2 The manifest from the resolver: neutral defaults (company name,
  the brand's light colour, the kit's icons, start URL = id = the brand
  home, scope ``/``, standalone, no shortcuts); the company's fields when
  filled; the hooks (start URL, id, shortcuts).
* UC-W3 The icons are served from the fields (bytes as uploaded) and the
  defaults (the kit's files); an uploaded non-raster file is never served.
* UC-W4 The routes are not multilang (no language redirect).
* UC-W5 The worker: headers (``Service-Worker-Allowed: /``, ``no-cache``),
  the version and precache substituted, no run-time cache write, the
  precached URLs answer 200 and hold no data page, the old ``pk-`` and
  ``sc-app-shell-`` caches deleted on activate; the version changes with
  the branding.
* UC-W6 The offline page carries no user data (fetched logged in), takes
  the app's name, colours and start URL.
* UC-W7 « More » lists « Install the app » for an app user (not in the
  tabs / rail); the install page renders in the app layout with the
  app's name, the per-device steps, the hidden installed state and prompt.
* UC-W8 The shell pages link the manifest and the iOS icon / title while
  the switch is on.
* UC-W9 Settings: the colours are validated; the settings fields write the
  company's.
* UC-W11 (task 5392) One portal app per instance: the brand the app
  registers (``_pk_apps()[app]['brand']``) gives the installed app its
  name, colours and start URL when the company's fields are empty; the
  company's fields still win.
"""
import base64
import io
import json
import re

from lxml import html as lxml_html
from PIL import Image

from odoo.exceptions import ValidationError
from odoo.modules.module import get_manifest
from odoo.tests import HttpCase, new_test_user, tagged
from odoo.tools import file_open

from odoo.addons.bemade_portal_kit_pwa.models.portal_kit import PK_PWA_ICONS

from odoo.addons.bemade_portal_kit.tests.common import pk_frontend_langs, pk_hooks

from .common import pk_pwa_shell

PUBLIC_URLS = ('/my/app.webmanifest', '/my/service-worker.js', '/my/app/offline', '/my/app/icon/icon-192.png')
ROLES = {'member': {'groups': ('base.group_portal',)}}


def _png(color, size=8):
    buf = io.BytesIO()
    Image.new('RGB', (size, size), color).save(buf, format='PNG')
    return buf.getvalue()


def _tree(response):
    return lxml_html.document_fromstring(response.text)


@tagged('post_install', '-at_install')
class TestPkPwa(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        pk_frontend_langs(cls.env)  # task 5392: the English texts asserted below
        cls.member = new_test_user(cls.env, login='pk_p6_member', groups='base.group_portal', lang='en_US',
                                   name='PK P6 Member')
        cls.member.partner_id.email = 'pk_p6_member@example.com'

    def setUp(self):
        super().setUp()
        shell = pk_pwa_shell(self.env, roles=ROLES)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        self.params = self.env['ir.config_parameter'].sudo()

    def _login(self):
        self.authenticate('pk_p6_member', 'pk_p6_member')

    def _switch_off(self):
        self.params.set_param('bemade_portal_kit.enabled', False)

    def _manifest(self):
        resp = self.url_open('/my/app.webmanifest', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/manifest+json', resp.headers['Content-Type'])
        self.assertIn('no-cache', resp.headers.get('Cache-Control', ''))
        return json.loads(resp.text)

    # ------------------------------------------------------------- UC-W1
    def test_switch_off_404(self):
        self._switch_off()
        for url in PUBLIC_URLS:
            self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 404, url)
        self._login()
        for url in PUBLIC_URLS:
            self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 404, url)
        resp = self.url_open('/my/app/install', allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))

    # ------------------------------------------------------------- UC-W2
    def test_manifest_defaults(self):
        manifest = self._manifest()
        self.assertEqual(list(manifest), ['name', 'short_name', 'id', 'start_url', 'scope', 'display',
                                          'background_color', 'theme_color', 'icons'])
        self.assertEqual(manifest['name'], self.env.company.name)
        self.assertEqual(manifest['short_name'], self.env.company.name)
        self.assertEqual((manifest['id'], manifest['start_url']), ('/my', '/my'))
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual((manifest['background_color'], manifest['theme_color']), ('#ffffff', '#ffffff'))
        self.assertEqual([(i['src'], i['sizes'], i['type'], i['purpose']) for i in manifest['icons']], [
            ('/my/app/icon/icon-192.png', '192x192', 'image/png', 'any'),
            ('/my/app/icon/icon-512.png', '512x512', 'image/png', 'any'),
            ('/my/app/icon/icon-maskable-512.png', '512x512', 'image/png', 'maskable'),
        ])

    def test_manifest_from_fields_and_hooks(self):
        self.env.company.write({
            'pk_pwa_name': 'PK Test App', 'pk_pwa_short_name': 'PK App',
            'pk_pwa_background_color': '#102030', 'pk_pwa_theme_color': '#405060',
        })
        manifest = self._manifest()
        self.assertEqual((manifest['name'], manifest['short_name']), ('PK Test App', 'PK App'))
        self.assertEqual((manifest['background_color'], manifest['theme_color']), ('#102030', '#405060'))
        # Theme colour empty: the background colour.
        self.env.company.pk_pwa_theme_color = False
        self.assertEqual(self._manifest()['theme_color'], '#102030')
        kit_cls = type(self.env['portal.kit'])
        from unittest.mock import patch
        with patch.object(kit_cls, '_pk_pwa_start_url', lambda self, app=None: '/my/t-home'), \
                patch.object(kit_cls, '_pk_pwa_shortcuts', lambda self, app=None: [{'name': 'T One', 'url': '/my/t1'}]):
            manifest = self._manifest()
        self.assertEqual((manifest['id'], manifest['start_url']), ('/my/t-home', '/my/t-home'))
        self.assertEqual(manifest['shortcuts'], [{'name': 'T One', 'url': '/my/t1'}])
        with patch.object(kit_cls, '_pk_pwa_manifest_id', lambda self, app=None: '/my/t-id'):
            self.assertEqual(self._manifest()['id'], '/my/t-id')

    # ------------------------------------------------------------ UC-W11
    def test_manifest_takes_the_app_brand(self):
        apps = {'pk_w_app': {'brand': {'name': 'Sample Brand App', 'home_url': '/my/pk-w-home',
                                       'theme_colors': {'light': '#0b2a4a', 'dark': '#000000'}}}}
        with pk_hooks(self.env, _pk_apps=lambda _orig: apps,
                      _pk_roles=lambda _orig: {'member': {'groups': ('base.group_portal',), 'app': 'pk_w_app'}}):
            manifest = self._manifest()
            self.assertEqual((manifest['name'], manifest['short_name']), ('Sample Brand App', 'Sample Brand App'))
            self.assertEqual((manifest['background_color'], manifest['theme_color']), ('#0b2a4a', '#0b2a4a'))
            self.assertEqual((manifest['id'], manifest['start_url']), ('/my/pk-w-home', '/my/pk-w-home'))
            self.env.company.write({'pk_pwa_name': 'PK Company App', 'pk_pwa_theme_color': '#405060'})
            manifest = self._manifest()
            self.assertEqual(manifest['name'], 'PK Company App')
            self.assertEqual((manifest['background_color'], manifest['theme_color']), ('#0b2a4a', '#405060'))

    # ------------------------------------------------------------- UC-W3
    def test_icons_defaults_and_fields(self):
        for name, field, default, _sizes, _purpose in PK_PWA_ICONS:
            resp = self.url_open('/my/app/icon/' + name)
            self.assertEqual(resp.status_code, 200, name)
            self.assertEqual(resp.headers['Content-Type'], 'image/png', name)
            with file_open('bemade_portal_kit_pwa/static/src/img/' + default, 'rb') as source:
                self.assertEqual(resp.content, source.read(), name)
        uploads = {}
        for index, (name, field, _default, _sizes, _purpose) in enumerate(PK_PWA_ICONS):
            uploads[name] = _png((index * 40, 10, 200))
            self.env.company[field] = base64.b64encode(uploads[name])
        for name, data in uploads.items():
            resp = self.url_open('/my/app/icon/' + name)
            self.assertEqual(resp.content, data, name)
        self.assertEqual(self.url_open('/my/app/icon/nope.png').status_code, 404)
        # An uploaded SVG (or anything not raster) is never served.
        self.env.company.pk_pwa_logo = base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>')
        resp = self.url_open('/my/app/icon/logo.png')
        self.assertEqual(resp.headers['Content-Type'], 'image/png')
        self.assertNotIn(b'<svg', resp.content)

    # ------------------------------------------------------------- UC-W4
    def test_routes_are_not_multilang(self):
        routing = {rule.rule: rule.endpoint.routing for rule in self.env['ir.http'].routing_map().iter_rules()}
        for url in ('/my/app.webmanifest', '/my/service-worker.js', '/my/app/offline', '/my/app/install',
                    '/my/app/icon/<string:name>'):
            self.assertIn(url, routing)
            self.assertIs(routing[url].get('multilang'), False, url)
        if 'website' in self.env:
            fr = self.env['res.lang']._activate_lang('fr_FR')
            for website in self.env['website'].search([]):
                website.language_ids = [(4, fr.id)]
            self.opener.cookies.set('frontend_lang', 'fr_FR')
            for url in PUBLIC_URLS:
                self.assertEqual(self.url_open(url, allow_redirects=False).status_code, 200, url)

    # ------------------------------------------------------------- UC-W5
    def test_service_worker(self):
        resp = self.url_open('/my/service-worker.js', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Service-Worker-Allowed'), '/')
        self.assertIn('no-cache', resp.headers.get('Cache-Control', ''))
        self.assertIn('javascript', resp.headers['Content-Type'])
        body = resp.text
        version = self.env['portal.kit']._pk_pwa_sw_version()
        self.assertTrue(version.startswith('%s-%s-' % (get_manifest('bemade_portal_kit_pwa')['version'],
                                                        get_manifest('bemade_portal_kit')['version'])), version)
        self.assertIn('const VERSION = "%s"' % version, body)
        self.assertIn('"pk-app-shell-" + VERSION', body)
        self.assertNotIn('__PK_SW_', body)
        # No run-time cache write: only the install-time precache.
        self.assertNotIn('.put(', body)
        self.assertEqual(body.count('addAll('), 1)
        self.assertIn('const OFFLINE_URL = "/my/app/offline"', body)
        precache = json.loads(re.search(r'const PRECACHE_STATIC = (\[.*?\]);', body).group(1))
        self.assertEqual(precache, ['/bemade_portal_kit_pwa/static/src/css/pk_offline.css',
                                    '/my/app/icon/logo.png', '/my/app/icon/icon-192.png'])
        # Never a page with data: the only /my/ URLs are the offline page and the icons.
        self.assertFalse([url for url in precache if url.startswith('/my/') and not url.startswith('/my/app/icon/')])
        for url in precache + ['/my/app/offline']:
            self.assertEqual(self.url_open(url).status_code, 200, url)
        # Old caches deleted on activate: older pk- ones and the former sc- ones.
        self.assertIn('caches.delete', body)
        self.assertIn('const OLD_PREFIXES = ["pk-app-shell-", "sc-app-shell-"]', body)
        # Navigations network-first, any path (no path filter).
        self.assertIn('fetch(request).catch(', body)
        navigate = re.search(r'request\.mode === "navigate"\) \{(.*?)return;', body, re.S)
        self.assertNotIn('pathname', navigate.group(1))

    def test_service_worker_version_follows_branding(self):
        kit = self.env['portal.kit']
        base = kit._pk_pwa_sw_version()
        self.assertEqual(kit._pk_pwa_sw_version(), base, 'stable')
        self.env.company.pk_pwa_name = 'PK Renamed App'
        renamed = kit._pk_pwa_sw_version()
        self.assertNotEqual(renamed, base)
        self.env.company.pk_pwa_logo = base64.b64encode(_png((1, 2, 3)))
        with_logo = kit._pk_pwa_sw_version()
        self.assertNotEqual(with_logo, renamed)
        self.env.company.pk_pwa_logo = base64.b64encode(_png((3, 2, 1)))
        self.assertNotEqual(kit._pk_pwa_sw_version(), with_logo, 'an icon edit rolls the cache')

    # ------------------------------------------------------------- UC-W6
    def test_offline_page_carries_no_user_data(self):
        self.env.company.write({'pk_pwa_name': 'PK Offline App', 'pk_pwa_background_color': '#112233'})
        self._login()
        resp = self.url_open('/my/app/offline', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        text = resp.text
        self.assertTrue(text.lstrip().startswith('<!DOCTYPE html>'))
        for leak in ('PK P6 Member', 'pk_p6_member', 'csrf_token', '__session_info__', 'session_info',
                     '/web/assets/'):
            self.assertNotIn(leak, text, leak)
        tree = _tree(resp)
        self.assertEqual(tree.xpath('//title/text()'), ['PK Offline App'])
        self.assertEqual(tree.xpath('//meta[@name="theme-color"]/@content'), ['#112233'])
        self.assertEqual(tree.xpath('//link[@rel="stylesheet"]/@href'),
                         ['/bemade_portal_kit_pwa/static/src/css/pk_offline.css'])
        self.assertEqual(tree.xpath('//a[contains(@class, "o_pk_offline_retry")]/@href'), ['/my'])
        self.assertEqual(tree.xpath('//main//img/@src'), ['/my/app/icon/logo.png'])
        style = tree.xpath('//body/@style')[0]
        self.assertIn('--pk-offline-bg: #112233', style)
        self.assertIn('--pk-offline-fg: #f8fafc', style, 'light text on a dark background')
        self.assertFalse(tree.xpath('//script'))

    # ------------------------------------------------------------- UC-W7
    def test_install_entry_and_page(self):
        self.env.company.pk_pwa_name = 'PK Install App'
        self._login()
        resp = self.url_open('/my/app/more')
        tree = _tree(resp)
        entry = tree.xpath('//main//a[@data-pk-nav-key="install"]')
        self.assertTrue(entry, 'the « More » entry')
        self.assertEqual(entry[0].get('href'), '/my/app/install')
        self.assertIn('Add the app to your home screen', resp.text)
        self.assertFalse(tree.xpath('//nav//a[@data-pk-nav-key="install"]'), 'not a tab nor in the rail')
        resp = self.url_open('/my/app/install', allow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        tree = _tree(resp)
        self.assertTrue(tree.xpath('//div[@data-pk-app-shell="1"]'), 'the app layout')
        hero = tree.xpath('//*[@data-pk-install]')[0]
        self.assertEqual(hero.xpath('.//strong/text()'), ['PK Install App'])
        self.assertEqual(hero.xpath('.//img/@src'), ['/my/app/icon/icon-192.png'])
        for key in ('ios', 'android', 'desktop'):
            self.assertTrue(tree.xpath('//*[@data-pk-install-steps="%s"]' % key), key)
        self.assertTrue(tree.xpath('//*[@data-pk-install-state="installed"][@hidden]'))
        self.assertIn('You are using PK Install App from your home screen.', resp.text)
        self.assertEqual(tree.xpath('//button[@data-pk-install-prompt]/text()'), ['Install PK Install App'])
        self.assertTrue(tree.xpath('//*[@data-pk-install-state="prompt"][@hidden]'))
        # The crumb / back: a sub-page of « More ».
        self.assertTrue(tree.xpath('//a[@href="/my/app/more"]'))
        self.assertEqual(self.env['portal.kit'].pk_pages()['pk_app_install'].url({}), '/my/app/install')
        self.assertEqual(self.env['portal.kit']._pk_help_page_key('pk_app_install'), 'install')

    # ------------------------------------------------------------- UC-W8
    def test_head_on_shell_pages(self):
        self.env.company.pk_pwa_short_name = 'PK Short'
        self._login()
        tree = _tree(self.url_open('/my/app/more'))
        self.assertEqual(tree.xpath('//head/link[@rel="manifest"]/@href'), ['/my/app.webmanifest'])
        # With ``website`` installed its layout adds the site favicon as an
        # apple-touch-icon first; the app's own icon must come last (the one
        # browsers keep).
        touch_icons = tree.xpath('//head/link[@rel="apple-touch-icon"]/@href')
        self.assertTrue(touch_icons)
        self.assertEqual(touch_icons[-1], '/my/app/icon/apple-touch-icon.png')
        self.assertEqual(tree.xpath('//head/meta[@name="apple-mobile-web-app-title"]/@content'), ['PK Short'])
        self.assertTrue(tree.xpath('//head/meta[@name="apple-mobile-web-app-capable"]'))
        self.assertTrue(tree.xpath('//head/meta[@name="apple-mobile-web-app-status-bar-style"]'))
        # Not on a stock portal page.
        self.assertNotIn('/my/app.webmanifest', self.url_open('/web/login').text)

    # ------------------------------------------------------------- UC-W9
    def test_settings(self):
        with self.assertRaises(ValidationError):
            self.env.company.pk_pwa_background_color = 'red'
        with self.assertRaises(ValidationError):
            self.env.company.pk_pwa_theme_color = '#12345'
        settings = self.env['res.config.settings'].create({
            'pk_pwa_name': 'PK Settings App', 'pk_pwa_theme_color': '#abcdef',
            'pk_pwa_icon_192': base64.b64encode(_png((9, 9, 9))),
        })
        settings.execute()
        self.assertEqual(self.env.company.pk_pwa_name, 'PK Settings App')
        self.assertEqual(self.env.company.pk_pwa_theme_color, '#abcdef')
        self.assertTrue(self.env.company.pk_pwa_icon_192)
        arch = self.env['res.config.settings'].get_view(view_type='form')['arch']
        for name in ('pk_pwa_name', 'pk_pwa_short_name', 'pk_pwa_background_color', 'pk_pwa_theme_color',
                     'pk_pwa_icon_192', 'pk_pwa_icon_512', 'pk_pwa_icon_maskable_512', 'pk_pwa_apple_touch_icon',
                     'pk_pwa_logo'):
            self.assertIn('name="%s"' % name, arch, name)

    # ------------------------------------------------------------ UC-W10
    def test_french(self):
        """The pages and the « More » entry in French (fr.po serves every
        French locale). The slots' texts are not checked: a consumer may word
        them its own way."""
        lang = self.env['res.lang']._activate_lang('fr_FR')
        self.env['ir.module.module']._load_module_terms(['bemade_portal_kit', 'bemade_portal_kit_pwa'], ['fr_FR'],
                                                        overwrite=True)
        if 'website' in self.env:
            for website in self.env['website'].search([]):
                website.language_ids = [(4, lang.id)]
        self.member.lang = 'fr_FR'
        self.env.company.pk_pwa_name = 'PK Appli'
        self.env.flush_all()
        self.env.registry.clear_cache()
        self._login()
        self.opener.cookies.set('frontend_lang', 'fr_FR')
        text = self.url_open('/my/app/install').text.replace('&#39;', "'")
        for term in ("Installer l'application", 'iPhone et iPad (Safari ou Chrome)', 'Touchez le bouton Partager',
                     "L'application est installée", "Vous utilisez PK Appli depuis votre écran d'accueil.",
                     'Installer PK Appli'):
            self.assertIn(term, text, term)
        text = self.url_open('/my/app/more').text.replace('&#39;', "'")
        self.assertIn("Ajouter l'application à l'écran d'accueil", text)
        text = self.url_open('/my/app/offline').text.replace('&#39;', "'")
        for term in ('Vous êtes hors ligne', 'Réessayer'):
            self.assertIn(term, text, term)
