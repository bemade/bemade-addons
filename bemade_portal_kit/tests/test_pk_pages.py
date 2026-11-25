# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Hook 4 — pages: parent / back / crumbs, return-URL allowlist. Synthetic
pages on ``res.partner`` only.

Acceptance criteria:

* UC-K13 ``pk_resolve(key, values)`` on a top-level page: no back
  (``parent_url`` False), no trail, the page's own context line or False.
* UC-K14 On a sub-page: ``parent_url`` is the declared parent's URL,
  ``crumbs`` the ancestors top first (label, url), ``context`` the page's
  own line, else the immediate parent's label.
* UC-K15 A return URL (``values['return_url']``, else the request's) that
  ``pk_match_url`` accepts becomes the parent: back + last crumb keep its
  query, the trail above it is that page's own. A page is never its own
  parent (same path + ``*id`` args as the request URL). Anything else —
  off-site, unregistered, unreadable record — leaves the declared parent.
* UC-K16 ``pk_match_url(url)`` returns ``(key, values)`` only for a safe
  same-site path that fullmatches a registered page ``path`` whose
  ``from_url`` resolves records the CURRENT user may read; a page without a
  ``path`` is never a target.
* UC-K17 A consumer adds pages through ``super()``; a page re-declared
  under an existing key replaces it.
"""
from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tools import Page, pk_arg, pk_readable, pk_static_page

from .common import pk_hook


def _partner_from(env, match, args):
    partner = pk_readable(env, 'res.partner', match.group(1))
    return {'partner': partner} if partner else None


def _query_partner_from(env, match, args):
    partner = pk_readable(env, 'res.partner', pk_arg(args, 'partner_id'))
    return {'partner': partner} if partner else None


def _pages():
    return [
        pk_static_page('kit_home', '/kit/home', 'Home'),
        pk_static_page('kit_list', '/kit/partners', 'Partners'),
        pk_static_page('kit_sub', '/kit/home/sub', 'Sub', parent=lambda v: ('kit_home', {})),
        Page('kit_partner', path=r'/kit/partner/(\d+)', from_url=_partner_from,
             url=lambda v: '/kit/partner/%s' % v['partner'].id,
             label=lambda v: v['partner'].sudo().name,
             parent=lambda v: ('kit_list', {})),
        Page('kit_partner_q', path=r'/kit/partner', from_url=_query_partner_from,
             url=lambda v: '/kit/partner?partner_id=%s' % v['partner'].id,
             label=lambda v: v['partner'].sudo().name,
             parent=lambda v: ('kit_list', {})),
        Page('kit_partner_edit',
             parent=lambda v: ('kit_partner', {'partner': v['partner']}),
             context=lambda v: 'Editing'),
        Page('kit_no_return', parent=lambda v: ('kit_home', {}),
             return_url=lambda v: None),
    ]


@tagged('post_install', '-at_install')
class TestPkPages(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Kit Partner One'})
        cls.other = cls.env['res.partner'].create({'name': 'Kit Partner Two'})
        cls.member = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'pk.pages.member', 'login': 'pk.pages.member@example.com',
            'group_ids': [Command.set([cls.env.ref('base.group_portal').id])],
        })

    def setUp(self):
        super().setUp()
        self.kit = self.env['portal.kit']
        self.enterContext(pk_hook(self.env, '_pk_pages', lambda _orig: _pages()))

    def _resolve(self, key, values, **kw):
        return self.kit.pk_resolve(key, values, **kw)

    # -- UC-K13 -----------------------------------------------------------
    def test_top_level(self):
        self.assertEqual(self._resolve('kit_home', {}),
                         {'parent_url': False, 'crumbs': [], 'context': False})
        # A return URL never adds a back chevron to a top-level page.
        nav = self._resolve('kit_home', {'return_url': '/kit/home/sub'})
        self.assertFalse(nav['parent_url'])

    def test_unknown_page(self):
        self.assertEqual(self._resolve('kit_nope', {}),
                         {'parent_url': False, 'crumbs': [], 'context': False})

    # -- UC-K14 -----------------------------------------------------------
    def test_sub_page_parent_and_crumbs(self):
        nav = self._resolve('kit_partner', {'partner': self.partner})
        self.assertEqual(nav, {'parent_url': '/kit/partners',
                               'crumbs': [('Partners', '/kit/partners')],
                               'context': 'Partners'})
        nav = self._resolve('kit_partner_edit', {'partner': self.partner})
        self.assertEqual(nav['parent_url'], '/kit/partner/%s' % self.partner.id)
        self.assertEqual(nav['crumbs'], [('Partners', '/kit/partners'),
                                         ('Kit Partner One', '/kit/partner/%s' % self.partner.id)])
        self.assertEqual(nav['context'], 'Editing')

    # -- UC-K15 -----------------------------------------------------------
    def test_valid_return_url_becomes_the_parent(self):
        nav = self._resolve('kit_partner', {'partner': self.partner,
                                            'return_url': '/kit/home/sub?tab=x'})
        self.assertEqual(nav['parent_url'], '/kit/home/sub?tab=x')
        self.assertEqual(nav['crumbs'], [('Home', '/kit/home'), ('Sub', '/kit/home/sub?tab=x')])
        self.assertEqual(nav['context'], 'Sub')

    def test_request_return_url_when_values_have_none(self):
        nav = self._resolve('kit_partner', {'partner': self.partner},
                            request_return_url='/kit/home')
        self.assertEqual(nav['crumbs'], [('Home', '/kit/home')])
        # values['return_url'] (even empty) wins over the request's.
        nav = self._resolve('kit_partner', {'partner': self.partner, 'return_url': None},
                            request_return_url='/kit/home')
        self.assertEqual(nav['parent_url'], '/kit/partners')

    def test_page_return_url_hook(self):
        nav = self._resolve('kit_no_return', {}, request_return_url='/kit/partners')
        self.assertEqual(nav['parent_url'], '/kit/home', 'return_url=None ignores the request')

    def test_bad_return_urls_keep_the_declared_parent(self):
        for bad in ('https://evil.example/kit/home', '//evil.example/kit/home',
                    'javascript:alert(1)', '/\\evil.example', '/kit/home\tx',
                    '/web/login', 'kit/home', '/kit/partner/abc', '/kit/partner/999999999'):
            nav = self._resolve('kit_partner', {'partner': self.partner, 'return_url': bad})
            self.assertEqual(nav['parent_url'], '/kit/partners', bad)

    def test_never_its_own_parent(self):
        url = '/kit/partner?partner_id=%s' % self.partner.id
        nav = self._resolve('kit_partner_q', {'partner': self.partner},
                            request_url=url + '&tab=a', request_return_url=url + '&tab=b')
        self.assertEqual(nav['parent_url'], '/kit/partners')

    # -- UC-K16 -----------------------------------------------------------
    def test_match_url(self):
        key, values = self.kit.pk_match_url('/kit/partner/%s' % self.partner.id)
        self.assertEqual((key, values['partner']), ('kit_partner', self.partner))
        key, values = self.kit.pk_match_url('/kit/partner?partner_id=%s&x=1' % self.partner.id)
        self.assertEqual((key, values['partner']), ('kit_partner_q', self.partner))
        self.assertEqual(self.kit.pk_match_url('/kit/home?x=1'), ('kit_home', {}))
        for bad in (None, '', '/kit/elsewhere', '/kit/partner/abc', '/kit/partner/999999999',
                    '/kit/partner?partner_id=abc', 'https://evil.example/kit/home',
                    '//evil.example/kit/home'):
            self.assertIsNone(self.kit.pk_match_url(bad), bad)

    def test_match_url_needs_read_access(self):
        member_kit = self.kit.with_user(self.member)
        own = self.member.partner_id
        self.assertEqual(member_kit.pk_match_url('/kit/partner/%s' % own.id)[0], 'kit_partner')
        self.assertIsNone(member_kit.pk_match_url('/kit/partner/%s' % self.other.id))

    def test_pages_without_path_are_never_targets(self):
        self.assertIsNone(self.kit.pk_match_url('/kit_partner_edit'))
        self.assertIn('kit_partner_edit', self.kit.pk_pages())
        self.assertIsNone(self.kit.pk_pages()['kit_partner_edit'].path)

    # -- UC-K17 -----------------------------------------------------------
    def test_consumer_adds_and_replaces_pages(self):
        def extend(orig):
            return list(orig) + [
                pk_static_page('kit_added', '/kit/added', 'Added',
                               parent=lambda v: ('kit_home', {})),
                pk_static_page('kit_sub', '/kit/home/sub', 'Sub again',
                               parent=lambda v: ('kit_list', {})),
            ]

        with pk_hook(self.env, '_pk_pages', extend):
            self.assertEqual(self._resolve('kit_added', {})['crumbs'], [('Home', '/kit/home')])
            self.assertEqual(self.kit.pk_match_url('/kit/added')[0], 'kit_added')
            nav = self._resolve('kit_partner', {'partner': self.partner,
                                                'return_url': '/kit/home/sub'})
            self.assertEqual(nav['crumbs'], [('Partners', '/kit/partners'),
                                             ('Sub again', '/kit/home/sub')])
