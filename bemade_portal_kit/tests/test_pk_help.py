# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the in-app help mapping (``portal.kit.help``).

* UC-H1 One row per key; the URL is an https address or a site path, never
  ``//…``, ``javascript:`` or plain text.
* UC-H2 ``pk_help_for(page, tab)``: the page's key (``_pk_help_keys``, else
  the page key), refined by the tab only for a key of ``_pk_help_tabbed``;
  the exact key's article, else its base's, else the help home; no article
  at all: no URL. Archived rows are not used.
* UC-H3 ``_pk_help_url(url)`` resolves each link: a rewrite applies, False
  leaves the link out (home included).
Synthetic keys and URLs only.
"""
import json
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from .common import pk_hooks


@tagged('post_install', '-at_install')
class TestPkHelp(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Help = self.env['portal.kit.help']
        self.Help.search([]).with_context(active_test=False).unlink()
        self.Help.with_context(active_test=False).search([]).unlink()
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_kit.help_home_url', '/pk/help/home')
        hooks = pk_hooks(self.env, _pk_help_keys=lambda _orig: {'pk_t_page': 'things'},
                         _pk_help_tabbed=lambda _orig: ('things',))
        hooks.__enter__()
        self.addCleanup(hooks.__exit__, None, None, None)
        self.kit_cls = type(self.env['portal.kit'])
        p = patch.object(self.kit_cls, '_pk_help_url', lambda self, url: url)
        p.start()
        self.addCleanup(p.stop)

    def test_url_check(self):
        for url in ('https://example.com/a', '/pk/help/1', '/pk/help?x=1'):
            self.Help.create({'key': 'ok_%s' % len(url), 'url': url})
        for url in ('//evil.example/x', 'javascript:alert(1)', 'help', 'http://example.com', '/a b'):
            with self.assertRaises(ValidationError, msg=url):
                self.Help.create({'key': 'bad', 'url': url})

    @mute_logger('odoo.sql_db')
    def test_unique_key(self):
        self.Help.create({'key': 'things', 'url': '/pk/1'})
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.Help.create({'key': 'things', 'url': '/pk/2'})

    def test_resolution(self):
        self.Help.create({'key': 'things', 'url': '/pk/things'})
        self.Help.create({'key': 'things.second', 'url': '/pk/things/second'})
        self.Help.create({'key': 'other', 'url': '/pk/other', 'active': False})
        help_ = self.Help.pk_help_for('pk_t_page')
        self.assertEqual((help_['key'], help_['base'], help_['url'], help_['tabbed']),
                         ('things', 'things', '/pk/things', True))
        self.assertEqual(help_['home'], '/pk/help/home')
        self.assertEqual(json.loads(help_['map_json']),
                         {'things': '/pk/things', 'things.second': '/pk/things/second'})
        self.assertEqual(self.Help.pk_help_for('pk_t_page', tab='second')['url'], '/pk/things/second')
        self.assertEqual(self.Help.pk_help_for('pk_t_page', tab='first')['url'], '/pk/things', 'the base')
        self.assertEqual(self.Help.pk_help_for('pk_t_page', tab='first')['key'], 'things.first')
        other = self.Help.pk_help_for('other')
        self.assertEqual((other['key'], other['url'], other['tabbed']), ('other', '/pk/help/home', False))
        self.assertEqual(self.Help.pk_help_for('other', tab='x')['key'], 'other', 'not tabbed')
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_kit.help_home_url', '')
        self.assertFalse(self.Help.pk_help_for('nothing')['url'])

    def test_resolver_hook(self):
        self.Help.create({'key': 'things', 'url': '/pk/things'})
        with patch.object(self.kit_cls, '_pk_help_url',
                          lambda self, url: False if url.startswith('/pk/things') else url + '#r'):
            help_ = self.Help.pk_help_for('pk_t_page')
            self.assertEqual(help_['url'], '/pk/help/home#r')
            self.assertEqual(json.loads(help_['map_json']), {})
