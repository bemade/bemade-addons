"""Task 1611 — shared helpers of the read-fragment tests (no test methods:
imported by the per-use-case modules only). Synthetic fixtures only."""
import re

from lxml import etree
from lxml import html as lxml_html

from odoo import fields

from odoo.addons.bemade_sports_clinic.controllers.app_shell import SC_FRAGMENTS_HEADER
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

_CSRF_RE = re.compile(r'(name="csrf_token"[^>]*value=")[^"]*(")')


def fragment_html(node):
    """A node serialized as the server serializes a fragment."""
    return etree.tostring(node, encoding='unicode', method='html', with_tail=False)


def no_csrf(html):
    """The CSRF token carries a per-second salt: two renders differ there only."""
    return _CSRF_RE.sub(r'\1\2', html or '')


class FragmentsMixin:
    """Helpers; mixed into an AppShellCommon-based case."""

    # -- requests ----------------------------------------------------------
    def _save(self, record, field, value, **extra):
        record.invalidate_recordset()
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value,
            'write_date': fields.Datetime.to_string(record.sudo().write_date),
            'csrf_token': self._csrf(), **extra,
        }, allow_redirects=False)

    def _saved(self, record, field, value, **extra):
        resp = self._save(record, field, value, **extra)
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def _fragments(self, url, keys):
        """GET ``url`` asking for ``keys`` -> the JSON answer."""
        resp = self.url_open(url, headers={SC_FRAGMENTS_HEADER: ','.join(keys)})
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertIn('application/json', resp.headers.get('Content-Type', ''))
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        return resp.json()

    def _fragment(self, url, key):
        """ONE fragment of ``url`` as a parsed node (fails when missing)."""
        payload = self._fragments(url, [key])
        self.assertIn(key, payload['fragments'], 'missing %s on %s: %s' % (key, url, payload['missing']))
        return lxml_html.fragment_fromstring(payload['fragments'][key])

    def _page(self, url):
        _text, tree = self._get(url)
        return tree

    @staticmethod
    def _node(tree, key):
        nodes = tree.xpath('//*[@data-sc-fragment="%s"]' % key)
        return nodes[0] if nodes else None

    @staticmethod
    def _text(node):
        return ' '.join(' '.join(node.itertext()).split())

    # -- assertions --------------------------------------------------------
    def assertFragmentMatchesPage(self, url, key):
        """A fragment answer is the very node of a full render (same QWeb,
        same values, same access rules)."""
        node = self._node(self._page(url), key)
        self.assertIsNotNone(node, 'no %s on %s' % (key, url))
        payload = self._fragments(url, [key])
        self.assertEqual(no_csrf(payload['fragments'][key]), no_csrf(fragment_html(node)), key)

    def assertRefreshes(self, payload, key):
        """``key`` (present on a page) is matched by the save's ``refresh``."""
        regs = [re.compile('^%s$' % ':'.join(
            '[^:]*'.join(re.escape(part) for part in seg.split('*'))
            for seg in pattern.split(':'))) for pattern in payload.get('refresh', [])]
        self.assertTrue(any(r.match(key) for r in regs),
                        '%s not refreshed by %s' % (key, payload.get('refresh')))


class FragmentsCommon(FragmentsMixin, AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
