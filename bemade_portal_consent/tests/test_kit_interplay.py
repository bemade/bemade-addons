# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Interplay with ``bemade_portal_kit`` (runs only when the kit is installed;
this addon does not depend on it).

Acceptance criteria
-------------------
* The kit's app pages (``/my/app/...``) are gated like any ``/my`` page.
* Kit installed, the user's profile language not the website default, a
  document pending: the request chain goes through the consent page once,
  with no redirect loop; after accepting, the user lands on the app page
  (the kit's language guard may add its own single redirect).
"""
import unittest
from urllib.parse import urljoin, urlsplit

from lxml import html as lxml_html

from odoo.fields import Command
from odoo.tests import HttpCase, tagged

from .common import ConsentFixtures, consent_hook


@tagged('post_install', '-at_install')
class TestConsentKitInterplay(ConsentFixtures, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'portal.kit' not in cls.env:
            raise unittest.SkipTest('bemade_portal_kit is not installed')
        cls._consent_setup()
        cls.v1._portal_consent_publish(requires_resign=True)
        lang = cls.env['res.lang']._activate_lang('fr_FR')
        if 'website' in cls.env:
            for website in cls.env['website'].search([]):
                website.language_ids = [Command.link(lang.id)]
        cls.portal_a.write({'lang': 'fr_FR', 'email': 'tc5390_portal_a@example.com'})

    def setUp(self):
        super().setUp()
        from odoo.addons.bemade_portal_kit.tests.common import pk_kit_shell
        for ctx in (pk_kit_shell(self.env, roles={'member': {'groups': ('base.group_portal',)}}),
                    consent_hook(self.env, lambda user: self.doc)):
            ctx.__enter__()
            self.addCleanup(ctx.__exit__, None, None, None)

    def _follow(self, url, max_hops=8, **kw):
        chain = []
        response = self.url_open(url, allow_redirects=False, **kw)
        while response.status_code in (301, 302, 303, 307, 308):
            chain.append(urlsplit(response.url).path)
            self.assertLess(len(chain), max_hops, 'redirect loop: %s' % chain)
            url = urljoin(response.url, response.headers['Location'])
            response = self.url_open(url, allow_redirects=False)
        chain.append(urlsplit(response.url).path)
        return response, chain

    def test_one_consent_redirect_no_loop(self):
        self.authenticate('tc5390_portal_a', 'tc5390_portal_a')
        response, chain = self._follow('/my/app/settings')
        self.assertEqual(response.status_code, 200, chain)
        self.assertTrue(chain[-1].endswith('/my/consent'), chain)
        self.assertEqual(sum(1 for p in chain if p.endswith('/my/consent')), 1, chain)

        tree = lxml_html.document_fromstring(response.text)
        form = tree.xpath('//form[@data-portal-consent-form]')[0]
        data = {name: form.xpath('.//input[@name="%s"]/@value' % name)[0]
                for name in ('csrf_token', 'version_id', 'redirect')}
        response = self.url_open(urljoin(response.url, '/my/consent/accept'), data=data, allow_redirects=False)
        response, chain = self._follow(urljoin(response.url, response.headers['Location']))
        self.assertEqual(response.status_code, 200, chain)
        self.assertTrue(chain[-1].endswith('/my/app/settings'), chain)
        self.assertTrue(lxml_html.document_fromstring(response.text).xpath('//div[@data-pk-app-shell="1"]'))
