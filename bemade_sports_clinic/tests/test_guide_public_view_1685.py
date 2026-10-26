"""Task 1685 — portal users get the public guide view with the full tree.
Synthetic articles only.

Acceptance criteria (they need website_knowledge, an enterprise SOFT
dependency: the tests skip cleanly when it is not installed, e.g. on the
addon CI and ``odoo-dev test``):

* AC-1 A portal user opening a PUBLISHED article they are not a member of
  gets website_knowledge's public view (``article_view_public``) with its
  sidebar container, and the header offers « Back to the app » (/my,
  « Retour à l'application » in French) instead of « Sign in ».
* AC-2 Unchanged: a portal user on an unpublished non-member article, a
  portal member of a published article (their knowledge web client), an
  internal user (backend redirect), a public visitor (public view with
  « Sign in »).
* AC-3 The public sidebar / children routes answer a logged-in portal user
  (the published-read rule).
"""
from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestGuidePublicView1685(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.wk = env['ir.module.module']._get('website_knowledge').state == 'installed'
        if not cls.wk:
            return
        # The update-time sync builds the header view; a test DB where
        # website_knowledge was installed AFTER this module needs it run.
        env['sc.help.article']._sc_sync_knowledge_public_view()
        Users = env['res.users'].with_context(no_reset_password=True)
        cls.portal = Users.create({
            'name': 'Guide Portal 1685', 'login': 'guide.portal.1685', 'password': 'guide.portal.1685',
            'group_ids': [Command.set([env.ref('base.group_portal').id])],
        })
        cls.member = Users.create({
            'name': 'Guide Member 1685', 'login': 'guide.member.1685', 'password': 'guide.member.1685',
            'group_ids': [Command.set([env.ref('base.group_portal').id])],
        })
        cls.internal = Users.create({
            'name': 'Guide Internal 1685', 'login': 'guide.internal.1685', 'password': 'guide.internal.1685',
            'group_ids': [Command.set([env.ref('base.group_user').id])],
        })
        Article = env['knowledge.article']
        cls.root = Article.create({
            'name': 'Synthetic guide 1685', 'body': '<p>Synthetic root</p>',
            'internal_permission': 'write', 'website_published': True,
        })
        cls.section = Article.create({
            'name': 'Synthetic section 1685', 'body': '<p>Synthetic section</p>',
            'parent_id': cls.root.id, 'website_published': True,
        })
        cls.page = Article.create({
            'name': 'Synthetic page 1685', 'body': '<p>Synthetic page</p>',
            'parent_id': cls.section.id, 'website_published': True,
        })
        cls.draft = Article.create({
            'name': 'Synthetic draft 1685', 'body': '<p>Synthetic draft</p>',
            'internal_permission': 'write', 'website_published': False,
        })
        cls.root.invite_members(cls.member.partner_id, 'read')

    def setUp(self):
        super().setUp()
        if not self.wk:
            self.skipTest('website_knowledge is not installed (soft dependency)')

    def _open(self, article):
        return self.url_open('/knowledge/article/%s' % article.id, allow_redirects=False)

    def test_ac1_portal_published_gets_public_view(self):
        self.authenticate('guide.portal.1685', 'guide.portal.1685')
        resp = self._open(self.section)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertIn('o_knowledge_public_view', resp.text)
        self.assertIn('o_knowledge_sidebar_container', resp.text)
        self.assertIn('data-sc-guide-back="1"', resp.text)
        self.assertIn('href="/my"', resp.text)
        self.assertIn('Back to the app', resp.text)
        self.assertNotIn('o_knowledge_article_log_in', resp.text)

    def test_ac1_back_to_app_in_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        self.portal.lang = 'fr_CA'
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        self.authenticate('guide.portal.1685', 'guide.portal.1685')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self._open(self.page)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Retour à l'application", resp.text.replace('&#39;', "'"))

    def test_ac2_portal_unpublished_unchanged(self):
        self.authenticate('guide.portal.1685', 'guide.portal.1685')
        resp = self._open(self.draft)
        self.assertNotIn('o_knowledge_public_view', resp.text)

    def test_ac2_portal_member_unchanged(self):
        self.authenticate('guide.member.1685', 'guide.member.1685')
        resp = self._open(self.root)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('o_knowledge_public_view', resp.text)

    def test_ac2_internal_unchanged(self):
        self.authenticate('guide.internal.1685', 'guide.internal.1685')
        resp = self._open(self.section)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('/odoo/knowledge/%s' % self.section.id, resp.headers['Location'])

    def test_ac2_public_visitor_unchanged(self):
        resp = self._open(self.section)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('o_knowledge_public_view', resp.text)
        self.assertIn('o_knowledge_article_log_in', resp.text)
        self.assertNotIn('data-sc-guide-back', resp.text)

    def test_ac3_public_sidebar_for_portal(self):
        self.authenticate('guide.portal.1685', 'guide.portal.1685')
        rows = self.make_jsonrpc_request('/knowledge/public/sidebar', {'article_id': self.page.id})
        ids = {row['id'] for row in rows}
        self.assertTrue({self.root.id, self.section.id} <= ids, rows)
        children = self.make_jsonrpc_request('/knowledge/public/children', {'article_id': self.section.id})
        self.assertEqual([row['id'] for row in children], [self.page.id])
