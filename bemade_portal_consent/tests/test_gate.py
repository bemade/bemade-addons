# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""The gate and the consent page (real HTTP requests).

Acceptance criteria
-------------------
* A pending portal user who requests ``/my``, ``/my/home``,
  ``/my/account`` (and ``/my/invoices`` when ``account`` is installed) is
  redirected (303) to ``/my/consent`` with ``redirect`` = the original page
  and its query string; with a language prefix (``/fr/my/home``) too.
* Exempt routes stay reachable: the consent page itself, the logout, the
  login page, public routes.
* A compliant user, a user with no documents and an internal user are
  never redirected.
* The consent page shows the pending document (name, version, text), an
  « I accept » form (POST, CSRF) and a « Log out » link; with two pending
  documents, they come one after the other; after the last one the user
  lands on the original page.
* Accepting logs the request's IP address and user agent; a POST without a
  CSRF token, or for a version that is not pending for the user, logs
  nothing.
* The ``redirect`` target is a relative path only: an absolute URL, a
  scheme-relative ``//host`` or ``/\\host`` falls back to ``/my``.
* The gated prefixes come from ``bemade_portal_consent.prefixes``.

Whatever the consumer installed with this addon (19.0.1.0.1): the site is
made English-default with French added (a French-default site would strip
the ``/fr`` prefix), and a consumer that sends ``/my`` to its own home is
allowed: « not gated » means no hop of the redirects goes to the consent
page and the page finally served answers 200.
"""
from urllib.parse import parse_qs, urlsplit

from lxml import html as lxml_html

from odoo.tests import HttpCase, tagged
from odoo.tools.misc import mute_logger

from .common import ConsentFixtures, consent_frontend_langs, consent_hook


def _split(location):
    parts = urlsplit(location)
    return parts.path, {k: v[0] for k, v in parse_qs(parts.query).items()}


@tagged('post_install', '-at_install')
class TestConsentGate(ConsentFixtures, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        consent_frontend_langs(cls.env, 'en_US', ('fr_FR',))
        cls._consent_setup()
        cls.v1._portal_consent_publish(requires_resign=True)
        cls.doc2 = cls.Document.create({'name': 'Sample code of conduct', 'code': 'tc5390_conduct'})
        cls.doc2_v1 = cls._new_version('<p>Sample conduct text.</p>', document=cls.doc2)
        cls.doc2_v1._portal_consent_publish(requires_resign=True)
        for user in (cls.portal_a, cls.portal_b, cls.staff):
            user.write({'email': '%s@example.com' % user.login})

    def setUp(self):
        super().setUp()
        self.docs_for = {self.portal_a.id: self.doc, self.portal_b.id: self.Document,
                         self.staff.id: self.doc}
        hook = consent_hook(self.env, lambda user: self.docs_for.get(user.id, self.Document))
        hook.__enter__()
        self.addCleanup(hook.__exit__, None, None, None)

    def _get(self, url, login='tc5390_portal_a'):
        if login:
            self.authenticate(login, login)
        return self.url_open(url, allow_redirects=False)

    def assertGated(self, url, expected_target):
        response = self._get(url)
        self.assertEqual(response.status_code, 303, url)
        path, query = _split(response.headers['Location'])
        self.assertTrue(path.endswith('/my/consent'), path)
        self.assertTrue(query.get('redirect', '').endswith(expected_target), query)
        return response

    def assertNotGated(self, url, login='tc5390_portal_a', follow=False):
        """Not sent to the consent page. ``follow``: each redirect hop is
        followed (a consumer may send ``/my`` to its own home) and none goes
        to the consent page; the last response is returned."""
        response = self._get(url, login=login)
        for _hop in range(5 if follow else 1):
            location = response.headers.get('Location', '')
            self.assertNotIn('/my/consent', urlsplit(location).path, url)
            if not (follow and response.is_redirect):
                break
            response = self.url_open(location, allow_redirects=False)
        return response

    def _csrf(self, response):
        tree = lxml_html.document_fromstring(response.text)
        return tree.xpath('//form[@data-portal-consent-form]//input[@name="csrf_token"]/@value')[0]

    # ---------------------------------------------------------------- gate
    def test_pending_user_is_gated(self):
        self.assertGated('/my', '/my')
        self.assertGated('/my/home', '/my/home')
        self.assertGated('/my/account?foo=1', '/my/account?foo=1')
        if 'account.move' in self.env:
            self.assertGated('/my/invoices', '/my/invoices')

    def test_language_prefix(self):
        # fr_FR is a frontend language other than the default (setUpClass):
        # its URL code prefixes the path.
        code = self.env['res.lang']._get_data(code='fr_FR').url_code
        response = self.assertGated('/%s/my/home' % code, '/my/home')
        path, _query = _split(response.headers['Location'])
        self.assertIn(path, ('/my/consent', '/%s/my/consent' % code))

    def test_exempt_routes(self):
        response = self.assertNotGated('/my/consent')
        self.assertEqual(response.status_code, 200)
        self.assertNotGated('/web/login')
        self.assertNotGated('/web/session/logout')

    def test_not_gated_users(self):
        self.docs_for[self.portal_a.id] = self.Document
        self.assertEqual(self.assertNotGated('/my/home', follow=True).status_code, 200, 'no documents')
        self.assertNotGated('/my/home', login='tc5390_staff')
        self.docs_for[self.portal_a.id] = self.doc
        self.v1._portal_consent_accept(self.portal_a)
        self.assertEqual(self.assertNotGated('/my/home', follow=True).status_code, 200, 'compliant')

    def test_prefixes_parameter(self):
        self.env['ir.config_parameter'].sudo().set_param('bemade_portal_consent.prefixes', '/my/account')
        self.assertNotGated('/my/home')
        self.assertGated('/my/account', '/my/account')

    # ---------------------------------------------------------------- page
    def test_consent_page_and_accept(self):
        self.docs_for[self.portal_a.id] = self.doc | self.doc2
        response = self._get('/my/consent?redirect=/my/account')
        self.assertEqual(response.status_code, 200)
        tree = lxml_html.document_fromstring(response.text)
        self.assertIn('Sample privacy notice', response.text)
        self.assertIn('Sample notice, first text.', response.text)
        form = tree.xpath('//form[@data-portal-consent-form][@method="post"]')
        self.assertTrue(form)
        self.assertEqual(form[0].xpath('.//input[@name="version_id"]/@value'), [str(self.v1.id)])
        self.assertEqual(form[0].xpath('.//input[@name="redirect"]/@value'), ['/my/account'])
        self.assertTrue(tree.xpath('//a[@data-portal-consent-logout][starts-with(@href, "/web/session/logout")]'))

        data = {'csrf_token': self._csrf(response), 'version_id': self.v1.id, 'redirect': '/my/account'}
        response = self.url_open('/my/consent/accept', data=data, allow_redirects=False,
                                 headers={'User-Agent': 'SampleBrowser/3.0'})
        self.assertEqual(response.status_code, 303)
        row = self.Acceptance.search([('user_id', '=', self.portal_a.id)])
        self.assertEqual(row.version_id, self.v1)
        self.assertEqual(row.user_agent, 'SampleBrowser/3.0')
        self.assertTrue(row.ip)

        response = self.url_open(response.headers['Location'], allow_redirects=False)
        self.assertEqual(response.status_code, 200, 'the second document')
        self.assertIn('Sample code of conduct', response.text)
        data = {'csrf_token': self._csrf(response), 'version_id': self.doc2_v1.id, 'redirect': '/my/account'}
        response = self.url_open('/my/consent/accept', data=data)
        self.assertEqual(urlsplit(response.url).path, '/my/account', 'lands on the original page')
        self.assertEqual(response.status_code, 200)

    def test_accept_needs_csrf_and_a_pending_version(self):
        self.authenticate('tc5390_portal_a', 'tc5390_portal_a')
        with mute_logger('odoo.http'):
            response = self.url_open('/my/consent/accept', data={'version_id': self.v1.id},
                                     allow_redirects=False)
        self.assertNotEqual(response.status_code, 303)
        page = self._get('/my/consent', login=None)
        data = {'csrf_token': self._csrf(page), 'version_id': self.doc2_v1.id}
        self.url_open('/my/consent/accept', data=data, allow_redirects=False)
        self.assertFalse(self.Acceptance.search([('user_id', '=', self.portal_a.id)]))

    def test_open_redirect(self):
        self.v1._portal_consent_accept(self.portal_a)
        for target in ('https://evil.example/x', '//evil.example/x', '/\\evil.example', 'javascript:alert(1)'):
            response = self._get('/my/consent?redirect=%s' % target)
            self.assertEqual(response.status_code, 303, target)
            parts = urlsplit(response.headers['Location'])
            self.assertNotIn('evil', parts.netloc, target)
            self.assertTrue(parts.path.endswith('/my'), target)
        self.docs_for[self.portal_a.id] = self.doc2
        page = self._get('/my/consent?redirect=https://evil.example/x')
        data = {'csrf_token': self._csrf(page), 'version_id': self.doc2_v1.id,
                'redirect': 'https://evil.example/x'}
        # Through the consent page to the target, the first hop that leaves
        # it checked (a consumer may then send /my further).
        response = self.url_open('/my/consent/accept', data=data, allow_redirects=False)
        for _hop in range(3):
            self.assertEqual(response.status_code, 303)
            if not urlsplit(response.headers['Location']).path.endswith('/my/consent'):
                break
            response = self.url_open(response.headers['Location'], allow_redirects=False)
        parts = urlsplit(response.headers['Location'])
        self.assertTrue(parts.path.endswith('/my'), parts.path)
        self.assertNotIn('evil', parts.netloc)
