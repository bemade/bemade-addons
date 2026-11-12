# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): screen refresh (read fragments), server side.

A read-only region of an app page carries ``data-pk-fragment="<key>"``. A
page route answers, when asked with the ``X-Pk-Fragments: k1,k2`` header,
only those regions of the SAME render as JSON. The kit's style guide
(``/pk/styleguide``) is such a page: it carries ``page:styleguide:*`` keys.

* UC-F1 ``pk_fragment_key(record, part)`` = ``<model>:<id>:<part>``;
  ``pk_now_ms()`` is the server time in ms.
* UC-F2 Key parsing (``pk_parse_fragment_keys``): None without the header;
  comma separated, stripped, de-duplicated, malformed keys dropped, at most
  ``PK_FRAGMENTS_MAX`` (200) keys.
* UC-F3 ``pk_extract_fragments(html, keys)``: the outer HTML of the first
  node of each key, and the page title.
* UC-F4 ``pk_refresh_patterns(spec, record, field)``: a bare part becomes
  the record's key, ``'*'`` refreshes for every field, a callable gives
  another record's keys, duplicates dropped.
* UC-F5 The fragment answer: ``{fragments, missing, title, rendered_at}``,
  ``Cache-Control: no-store``, ``Vary: X-Pk-Fragments``; a fragment is the
  very node of the full render; a normal request gets the page.
* UC-F6 Fillers (``portal.kit._pk_fragment_fillers()``): each one may add
  keys the render missed; a filled key is no longer ``missing``.
"""
import time

from lxml import etree
from lxml import html as lxml_html

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit.tools import (
    PK_FRAGMENTS_HEADER, PK_FRAGMENTS_MAX, pk_extract_fragments, pk_fragment_key, pk_now_ms,
    pk_parse_fragment_keys, pk_refresh_patterns,
)

from .common import pk_hook

URL = '/pk/styleguide'


@tagged('post_install', '-at_install')
class TestPkFragmentHelpers(HttpCase):

    def test_key_and_clock(self):
        partner = self.env['res.partner'].create({'name': 'Synthetic'})
        self.assertEqual(pk_fragment_key(partner, 'hero'), 'res.partner:%s:hero' % partner.id)
        before = int(time.time() * 1000)
        self.assertTrue(before <= pk_now_ms() <= int(time.time() * 1000))
        self.assertEqual(PK_FRAGMENTS_HEADER, 'X-Pk-Fragments')

    def test_parse_keys(self):
        self.assertIsNone(pk_parse_fragment_keys(None))
        self.assertEqual(pk_parse_fragment_keys(''), [])
        self.assertEqual(
            pk_parse_fragment_keys(' a:1:b , a:1:b,page:x:*,bad key,<x>,a:1:b;drop, sc.dashboard:todo:*:list'),
            ['a:1:b', 'page:x:*', 'sc.dashboard:todo:*:list'])
        many = ','.join('m:%s:p' % i for i in range(PK_FRAGMENTS_MAX + 50))
        self.assertEqual(len(pk_parse_fragment_keys(many)), PK_FRAGMENTS_MAX)

    def test_extract(self):
        html = ('<html><head><title> T </title></head><body>'
                '<div data-pk-fragment="a:1:x"><b>one</b></div>'
                '<div data-pk-fragment="a:1:x">dup</div>'
                '<p data-pk-fragment="a:1:y" class="c">two</p></body></html>')
        found, title = pk_extract_fragments(html, ['a:1:x', 'a:1:y', 'a:1:z'])
        self.assertEqual(title, 'T')
        self.assertEqual(found, {
            'a:1:x': '<div data-pk-fragment="a:1:x"><b>one</b></div>',
            'a:1:y': '<p data-pk-fragment="a:1:y" class="c">two</p>',
        })

    def test_refresh_patterns(self):
        partner = self.env['res.partner'].create({'name': 'Synthetic'})
        other = self.env['res.partner'].create({'name': 'Other'})
        spec = {'fields': ('name', 'email'), 'refresh': {
            '*': ['*', 'page:list:*'],
            'name': ['hero', lambda p: ['res.partner:%s:*' % other.id, 'page:list:*', ''], 'hero'],
        }}
        pid = partner.id
        self.assertEqual(pk_refresh_patterns(spec, partner, 'name'), [
            'res.partner:%s:*' % pid, 'page:list:*', 'res.partner:%s:hero' % pid, 'res.partner:%s:*' % other.id])
        self.assertEqual(pk_refresh_patterns(spec, partner, 'email'), ['res.partner:%s:*' % pid, 'page:list:*'])
        self.assertEqual(pk_refresh_patterns({}, partner, 'email'), [])
        self.assertEqual(pk_refresh_patterns(None, partner, 'email'), [])


@tagged('post_install', '-at_install')
class TestPkFragmentResponse(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(cls.env, login='pk_frag_internal', groups='base.group_user')

    def setUp(self):
        super().setUp()
        self.authenticate('pk_frag_internal', 'pk_frag_internal')

    def _ask(self, keys):
        return self.url_open(URL, headers={PK_FRAGMENTS_HEADER: ','.join(keys)})

    def test_page_and_fragments(self):
        page = self.url_open(URL)
        self.assertEqual(page.status_code, 200)
        self.assertIn('text/html', page.headers['Content-Type'])
        tree = lxml_html.document_fromstring(page.text)
        node = tree.xpath('//*[@data-pk-fragment="page:styleguide:stats"]')[0]
        root = tree.xpath('//*[@data-pk-rendered-at]')
        self.assertTrue(root, 'the shell root carries its render time')

        before = pk_now_ms()
        res = self._ask(['page:styleguide:stats', 'page:styleguide:nowhere'])
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/json', res.headers['Content-Type'])
        self.assertEqual(res.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(res.headers.get('Vary'), PK_FRAGMENTS_HEADER)
        body = res.json()
        self.assertEqual(set(body), {'fragments', 'missing', 'title', 'rendered_at'})
        self.assertEqual(body['missing'], ['page:styleguide:nowhere'])
        self.assertEqual(
            body['fragments']['page:styleguide:stats'],
            etree.tostring(node, encoding='unicode', method='html', with_tail=False))
        self.assertTrue(body['title'])
        self.assertGreaterEqual(body['rendered_at'], before)

    def test_filler_hook(self):
        def filler(found, keys):
            for key in keys:
                if key.startswith('page:styleguide:copy-') and key not in found:
                    found[key] = found['page:styleguide:stats'].replace(
                        'page:styleguide:stats', key)

        with pk_hook(self.env, '_pk_fragment_fillers', lambda orig: list(orig) + [filler]):
            body = self._ask(['page:styleguide:stats', 'page:styleguide:copy-1', 'page:styleguide:x']).json()
        self.assertIn('data-pk-fragment="page:styleguide:copy-1"', body['fragments']['page:styleguide:copy-1'])
        self.assertEqual(body['missing'], ['page:styleguide:x'])
