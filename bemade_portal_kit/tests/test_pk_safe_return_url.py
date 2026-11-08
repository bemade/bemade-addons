# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The ONE return-URL validator, ``pk_safe_return_url``.

Acceptance criteria:

* UC-K18 A same-site path (``/…``) is returned as is (a plain space allowed).
* UC-K19 Off-site and dangerous values give the fallback: empty / non-string,
  a scheme (``https://``, ``javascript:``), scheme-relative ``//…``, a
  backslash (``/\\evil`` = ``//evil`` in a browser), any control character,
  a relative path.
* UC-K20 ``prefixes`` further restricts the accepted paths (allowlist).
* UC-K21 ``portal.kit.pk_safe_return_url`` is the same function.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tools import pk_safe_return_url as safe


@tagged('post_install', '-at_install')
class TestPkSafeReturnUrl(TransactionCase):

    def test_same_site_paths(self):
        for good in ('/kit/home', '/kit/list?q=a b&x=1', '/'):
            self.assertEqual(safe(good, 'fb'), good)

    def test_refused(self):
        for bad in (None, '', 42, b'/kit', 'https://evil.example/kit', 'http:/kit',
                    'javascript:alert(1)', '//evil.example', '/\\evil.example',
                    '/kit\\x', '/\t/evil', '/a\nb', '/a\rb', '/a\x00b', '/a\x7fb', 'kit/home',
                    ' /kit/home'):
            self.assertEqual(safe(bad, 'fb'), 'fb', repr(bad))
            self.assertIsNone(safe(bad, None), repr(bad))

    def test_prefix_allowlist(self):
        prefixes = ('/kit/events', '/kit/home')
        self.assertEqual(safe('/kit/events?x=1', None, prefixes=prefixes), '/kit/events?x=1')
        self.assertEqual(safe('/kit/home', None, prefixes=prefixes), '/kit/home')
        self.assertIsNone(safe('/kit/teams', None, prefixes=prefixes))
        self.assertIsNone(safe('//kit/events', None, prefixes=prefixes))

    def test_model_method_is_the_same_rule(self):
        kit = self.env['portal.kit']
        self.assertEqual(kit.pk_safe_return_url('/kit/home', None), '/kit/home')
        self.assertEqual(kit.pk_safe_return_url('//evil', 'fb'), 'fb')
        self.assertIsNone(kit.pk_safe_return_url('/kit/teams', None, prefixes=('/kit/home',)))
