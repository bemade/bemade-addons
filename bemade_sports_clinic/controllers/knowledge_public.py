"""Task 1685 — the user guide for portal users: the public guide view with
its full tree.

website_knowledge only sends PUBLIC visitors to its public article view; a
logged-in portal user falls through to the knowledge web client
(``knowledge.knowledge_portal_view``), whose sidebar lists only the articles
the user is a member of — none for the published guide, so the tree is
empty and the user is stranded. A portal user opening a PUBLISHED article
they are not a member of gets the public view instead (sidebar fed by
``/knowledge/public/sidebar`` / ``children``, published-only rule).
Members, unpublished articles, internal users and public visitors keep
website_knowledge's own behaviour.

Task 1720: the app's « ? », « Aide » and « Guide d'utilisation » links go
through ``/my/guide/<id>``, which renders the same public view for EVERY
logged-in user — internal users included (MC: the backend Knowledge app's
tree / breadcrumbs are poor for the shared guide). A published article gets
the public view (sidebar tree, « ← Application » header); anything else
falls back to the normal ``/knowledge/article/<id>`` route. Editors keep the
backend Knowledge app from the backend menu. The route only exists while
website_knowledge is installed (same class), and the links are only
rewritten then (``sc.help.article._sc_help_links``).

website_knowledge is a SOFT dependency (enterprise; the addon CI may not
have it): the class only exists when its code is importable, and Odoo only
routes it when website_knowledge is installed (a controller subclass of a
module that is not installed is never reached by the routing).
"""
from odoo import http
from odoo.http import request

try:
    from odoo.addons.website_knowledge.controllers.main import KnowledgeWebsiteController
except ImportError:  # website_knowledge (enterprise) not on the addons path
    KnowledgeWebsiteController = None


if KnowledgeWebsiteController is not None:

    class ScKnowledgeWebsiteController(KnowledgeWebsiteController):

        @http.route()
        def redirect_to_article(self, **kwargs):
            user = request.env.user
            if not user._is_public() and not user._is_internal():
                article_id = kwargs.get('article_id')
                public = request.env['knowledge.article'].sudo().browse(article_id).exists()
                if public and public.website_published:
                    # The viewer's own permission (membership), not the
                    # published-read rule.
                    mine = request.env['knowledge.article'].browse(public.id)
                    if not mine.user_has_access:
                        return self._redirect_to_public_view(public, kwargs.get('no_sidebar', False))
            return super().redirect_to_article(**kwargs)

        @http.route('/my/guide/<int:article_id>', type='http', auth='user', website=True,
                    sitemap=False, multilang=False)
        def sc_guide_article(self, article_id, **kwargs):
            """Task 1720: the guide's public view for any logged-in user."""
            public = request.env['knowledge.article'].sudo().browse(article_id).exists()
            if public and public.website_published:
                return self._redirect_to_public_view(public, kwargs.get('no_sidebar', False))
            return request.redirect('/knowledge/article/%s' % article_id)
