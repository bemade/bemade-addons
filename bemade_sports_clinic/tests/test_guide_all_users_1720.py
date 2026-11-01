"""Task 1720 — the app's guide links open the public guide view for every
logged-in user, internal users included. Synthetic articles only.

Acceptance criteria (website_knowledge is an enterprise SOFT dependency:
the tests needing it skip cleanly when it is not installed, as in #1685):

* AC-1 ``/my/guide/<id>`` of a PUBLISHED article renders website_knowledge's
  public view (sidebar container, « Back to the app » header) for an
  internal user AND a portal user.
* AC-2 An unpublished (or missing) article falls back to the normal route
  (``/knowledge/article/<id>``).
* AC-3 The app's help links (« ? », « Aide », « Guide d'utilisation »)
  configured as ``/knowledge/article/<id>`` (home and mapping) are rendered
  as ``/my/guide/<id>``; an https address is unchanged.
* AC-4 The internal user's public view sidebar answers (published read).
* AC-5 #1685's override of direct ``/knowledge/article`` links is kept (its
  own tests).
"""
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.sc_help_article import SC_HELP_HOME_PARAM
from odoo.addons.bemade_sports_clinic.tests.test_guide_public_view_1685 import TestGuidePublicView1685


@tagged('post_install', '-at_install')
class TestGuideAllUsers1720(TestGuidePublicView1685):

    # Only this class's tests (the inherited 1685 ones run in their own class).
    test_ac1_portal_published_gets_public_view = test_ac1_back_to_app_in_french = None
    test_ac4_compact_header = test_ac2_portal_unpublished_unchanged = None
    test_ac2_portal_member_unchanged = test_ac2_internal_unchanged = None
    test_ac2_public_visitor_unchanged = test_ac3_public_sidebar_for_portal = None

    def _guide(self, article_id):
        return self.url_open('/my/guide/%s' % article_id, allow_redirects=False)

    def _public_view(self, resp):
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertIn('o_knowledge_public_view', resp.text)
        self.assertIn('o_knowledge_sidebar_container', resp.text)
        self.assertIn('data-sc-guide-back="1"', resp.text)
        self.assertNotIn('o_knowledge_article_log_in', resp.text)

    # -- AC-1 ------------------------------------------------------------
    def test_internal_user_gets_public_view(self):
        self.authenticate('guide.internal.1685', 'guide.internal.1685')
        self._public_view(self._guide(self.section.id))

    def test_portal_user_gets_public_view(self):
        self.authenticate('guide.portal.1685', 'guide.portal.1685')
        self._public_view(self._guide(self.page.id))
        # A member too (the guide view, not their knowledge web client).
        self.authenticate('guide.member.1685', 'guide.member.1685')
        self._public_view(self._guide(self.root.id))

    # -- AC-2 ------------------------------------------------------------
    def test_unpublished_falls_back(self):
        self.authenticate('guide.internal.1685', 'guide.internal.1685')
        resp = self._guide(self.draft.id)
        self.assertIn(resp.status_code, (302, 303))
        self.assertTrue(resp.headers['Location'].endswith('/knowledge/article/%s' % self.draft.id))
        resp = self._guide(999999999)
        self.assertIn(resp.status_code, (302, 303))

    # -- AC-3 ------------------------------------------------------------
    def test_help_links_rewritten(self):
        Help = self.env['sc.help.article'].sudo()
        self.env['ir.config_parameter'].sudo().set_param(
            SC_HELP_HOME_PARAM, '/knowledge/article/%s' % self.root.id)
        Help.create({'key': 'players', 'url': '/knowledge/article/%s' % self.section.id})
        Help.create({'key': 'teams', 'url': 'https://guide.example.com/teams'})
        links = Help._sc_help_links()
        self.assertEqual(links['home'], '/my/guide/%s' % self.root.id)
        self.assertEqual(links['map']['players'], '/my/guide/%s' % self.section.id)
        self.assertEqual(links['map']['teams'], 'https://guide.example.com/teams')
        help_ = Help._sc_help_for('sc_app_players')
        self.assertEqual(help_['url'], '/my/guide/%s' % self.section.id)
        self.assertIn('/my/guide/%s' % self.section.id, help_['map_json'])

    # -- AC-4 ------------------------------------------------------------
    def test_public_sidebar_for_internal(self):
        self.authenticate('guide.internal.1685', 'guide.internal.1685')
        rows = self.make_jsonrpc_request('/knowledge/public/sidebar', {'article_id': self.page.id})
        ids = {row['id'] for row in rows}
        self.assertTrue({self.root.id, self.section.id} <= ids, rows)


@tagged('post_install', '-at_install')
class TestGuideUrlNoKnowledge1720(TestGuidePublicView1685):
    """Runs everywhere: an https help address is never rewritten."""

    test_ac1_portal_published_gets_public_view = test_ac1_back_to_app_in_french = None
    test_ac4_compact_header = test_ac2_portal_unpublished_unchanged = None
    test_ac2_portal_member_unchanged = test_ac2_internal_unchanged = None
    test_ac2_public_visitor_unchanged = test_ac3_public_sidebar_for_portal = None

    def setUp(self):
        super(TestGuidePublicView1685, self).setUp()

    def test_https_unchanged(self):
        Help = self.env['sc.help.article']
        self.assertEqual(Help._sc_guide_url('https://guide.example.com/a'), 'https://guide.example.com/a')
        self.assertEqual(Help._sc_guide_url('/knowledge/article/12#s'), '/my/guide/12#s')
