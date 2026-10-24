"""Task 1660 — in-app help. Synthetic fixtures only (example.com URLs).

Acceptance criteria covered here:

* AC-1 Per role (coach, therapist, clinic admin): the app bar « ? » links to
  the article mapped to the page (team → its article), in a new tab
  (``target=_blank rel=noopener``); a tabbed page uses « <page>.<tab> »
  (player.injuries) then « <page> »; an unmapped page opens the guide home;
  the user-menu « Aide » and the « Plus » row « Guide d'utilisation » open the
  guide home; no link ever points to /my?subpath=knowledge.
* AC-2 Nothing configured (no home, no mapping) → no help entry at all; a
  /knowledge/… URL is offered only while website_knowledge is installed.
* AC-3 The mapping is clinic-admin (or system) only: CRUD for them, an
  AccessError for an internal therapist and a portal user; a URL must be a
  public guide article or an https address.
* AC-4 (tour) Guide videos: a same-origin /web/content link marked
  « o_fc_video » whose attachment is a video/* becomes a playable
  <video controls playsinline> (the link is hidden under it); another origin,
  a non-attachment path, a non-video attachment or a link inside an editor
  stays a plain link.
* AC-5 (review 2026-10-24) The public /knowledge/article/<id> page upgrades
  the link both logged out (frontend layout, web.assets_frontend) and for a
  logged-in portal user (Knowledge's portal web client,
  knowledge.webclient); the class « o_fc_video » survives the Html field
  sanitizer.
"""
import base64
import unittest

from lxml import html as lxml_html

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import html_sanitize
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.sc_help_article import SC_HELP_HOME_PARAM
from odoo.addons.bemade_sports_clinic.tests.test_internal_tp_parity_1577 import Parity1577Common

HOME = 'https://guide.example.com/home'
TEAM = 'https://guide.example.com/team'
INJURIES = 'https://guide.example.com/injuries'


class Help1660Common(Parity1577Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _configure(self):
        self.env['ir.config_parameter'].sudo().set_param(SC_HELP_HOME_PARAM, HOME)
        Help = self.env['sc.help.article'].sudo()
        Help.create({'key': 'team', 'url': TEAM})
        Help.create({'key': 'player.injuries', 'url': INJURIES})

    def _tree(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        self.assertNotIn('subpath=knowledge', resp.text)
        return lxml_html.fromstring(resp.text)

    @staticmethod
    def _help(tree):
        links = tree.xpath('//a[@data-sc-help]')
        return links[0] if links else None


@tagged('post_install', '-at_install')
class TestInAppHelp1660(Help1660Common):

    # -- AC-1 -------------------------------------------------------------
    def test_help_links_per_role(self):
        self._configure()
        for login in (self._login_coach, self._login_tp, self._login_cadmin):
            login()
            tree = self._tree('/my/team?team_id=%s' % self.team_a.id)
            link = self._help(tree)
            self.assertIsNotNone(link, login.__name__)
            self.assertEqual(link.get('href'), TEAM, login.__name__)
            self.assertEqual((link.get('target'), link.get('rel')), ('_blank', 'noopener'))
            menu = tree.xpath('//*[@data-sc-user-menu-popup]//a[@data-sc-help-home-link]')
            self.assertEqual([a.get('href') for a in menu], [HOME], login.__name__)
            self.assertEqual(menu[0].get('target'), '_blank')
            # Unmapped page → the guide home.
            self.assertEqual(self._help(self._tree('/my/players')).get('href'), HOME, login.__name__)
            more = self._tree('/my/app/more')
            row = more.xpath('//*[@data-sc-section="more.guide"]//a[@data-sc-help-home-link]')
            self.assertEqual([a.get('href') for a in row], [HOME], login.__name__)
            self.assertEqual(row[0].get('target'), '_blank')

    def test_tabbed_page_key(self):
        self._configure()
        self._login_tp()
        tree = self._tree('/my/player?player_id=%s&tab=injuries' % self.player.id)
        link = self._help(tree)
        self.assertEqual(link.get('href'), INJURIES)
        self.assertEqual(link.get('data-sc-help-key'), 'player.injuries')
        tree = self._tree('/my/player?player_id=%s&tab=info' % self.player.id)
        self.assertEqual(self._help(tree).get('href'), HOME)

    # -- AC-2 -------------------------------------------------------------
    def test_nothing_configured_no_entry(self):
        self._login_tp()
        tree = self._tree('/my/team?team_id=%s' % self.team_a.id)
        self.assertIsNone(self._help(tree))
        self.assertFalse(tree.xpath('//a[@data-sc-help-home-link]'))
        self.assertFalse(self._tree('/my/app/more').xpath('//*[@data-sc-section="more.guide"]'))

    def test_knowledge_url_needs_website_knowledge(self):
        self.env['ir.config_parameter'].sudo().set_param(SC_HELP_HOME_PARAM, '/knowledge/article/1')
        installed = self.env['ir.module.module']._get('website_knowledge').state == 'installed'
        self._login_tp()
        link = self._help(self._tree('/my/players'))
        if installed:
            self.assertEqual(link.get('href'), '/knowledge/article/1')
        else:
            self.assertIsNone(link)

    # -- AC-3 -------------------------------------------------------------
    def test_mapping_admin_only(self):
        rec = self.env['sc.help.article'].with_user(self.cadmin).create(
            {'key': 'events', 'url': '/knowledge/article/179'})
        rec.with_user(self.cadmin).write({'url': 'https://guide.example.com/events'})
        with mute_logger('odoo.models', 'odoo.addons.base.models.ir_model'):
            for user in (self.itp, self.tp, self.coach):
                with self.assertRaises(AccessError):
                    self.env['sc.help.article'].with_user(user).create({'key': 'x', 'url': HOME})
                with self.assertRaises(AccessError):
                    rec.with_user(user).write({'url': HOME})
        rec.with_user(self.cadmin).unlink()

    def test_url_must_be_a_guide_article(self):
        Help = self.env['sc.help.article']
        for bad in ('/my?subpath=knowledge', '/my/home', 'javascript:alert(1)',
                    'http://guide.example.com/x', 'https://x.example.com/my?subpath=knowledge'):
            with self.assertRaises(ValidationError, msg=bad), self.env.cr.savepoint():
                Help.create({'key': 'bad', 'url': bad})
        self.assertTrue(Help.create({'key': 'ok', 'url': '/knowledge/article/163'}))


@tagged('post_install', '-at_install')
class TestInAppHelpTour1660(Help1660Common):
    browser_size = '390x844'

    def test_video_links_upgrade(self):
        video, text = _guide_attachments(self.env)
        self.start_tour(
            f'/my/home?video={video.id}&text={text.id}', 'sc_1660_video_links',
            login='pc.tp@example.com')


# A playable 16×16, 0.2 s black VP8 WebM (synthetic, generated with ffmpeg's
# lavfi « color » source): every Chrome build decodes it, so the player is not
# dropped on a decode error while the tour looks at it.
TINY_WEBM_B64 = (
    'GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYECGFOAZwEAAAAAAAHpEU2bdLpN'
    'u4tTq4QVSalmU6yBoU27i1OrhBZUrmtTrIHYTbuMU6uEElTDZ1OsggElTbuMU6uEHFO7a1Os'
    'ggHT7AEAAAAAAABZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSalmsirX'
    'sYMPQkBNgI1MYXZmNjIuMTIuMTAxV0GNTGF2ZjYyLjEyLjEwMUSJiEBpAAAAAAAAFlSua8iu'
    'AQAAAAAAAD/XgQFzxYhnzPgpSu7/8JyBACK1nIN1bmSIgQCGhVZfVlA4g4EBI+ODhAvrwgDg'
    'kLCBELqBEJqBAlWwhFW5gQESVMNn/HNzoGPAgGfImkWjh0VOQ09ERVJEh41MYXZmNjIuMTIu'
    'MTAxc3PWY8CLY8WIZ8z4KUru//BnyKFFo4dFTkNPREVSRIeUTGF2YzYyLjI4LjEwMSBsaWJ2'
    'cHhnyKFFo4hEVVJBVElPTkSHkzAwOjAwOjAwLjIwMDAwMDAwMAAfQ7Z1qOeBAKOjgQAAgBAC'
    'AJ0BKhAAEAAARwiFhYiFhIgCAgAMDWAA/v+rUIAcU7trkbuPs4EAt4r3gQHxggGm8IED'
)


def _guide_attachments(env):
    """A public video attachment and a public non-video one."""
    Attachment = env['ir.attachment'].sudo()
    video = Attachment.create({
        'name': 'guide-1660.webm', 'raw': base64.b64decode(TINY_WEBM_B64),
        'mimetype': 'video/webm', 'public': True})
    text = Attachment.create({
        'name': 'guide-1660.txt', 'raw': b'not a video', 'mimetype': 'text/plain',
        'public': True})
    assert video.mimetype == 'video/webm' and text.mimetype.startswith('text/')
    return video, text


VIDEO_JS = 'bemade_sports_clinic/static/src/js/sc_guide_video.js'


@tagged('post_install', '-at_install')
class TestGuideVideoAssets1660(Help1660Common):

    def _bundle(self, name):
        return [path for path, *_rest in self.env['ir.asset']._get_asset_paths(name, {})]

    def test_player_in_the_frontend_bundles(self):
        """Anonymous visitors: the public article layout loads
        web.assets_frontend (lazily, through web.assets_frontend_lazy)."""
        for bundle in ('web.assets_frontend', 'web.assets_frontend_lazy'):
            self.assertTrue(
                any(p.endswith(VIDEO_JS) for p in self._bundle(bundle)), bundle)

    def test_player_in_the_knowledge_portal_client(self):
        """Logged-in portal users get Knowledge's portal web client."""
        if 'knowledge.article' not in self.env:
            self.skipTest('knowledge is not installed')
        self.assertTrue(any(p.endswith(VIDEO_JS) for p in self._bundle('knowledge.webclient')))

    def test_class_survives_the_sanitizer(self):
        body = '<p><a class="o_fc_video" href="/web/content/42">Vidéo</a></p>'
        self.assertIn('class="o_fc_video"', html_sanitize(body))
        if 'knowledge.article' in self.env:
            article = self.env['knowledge.article'].create({'name': 'Guide 1660', 'body': body})
            self.assertIn('class="o_fc_video"', str(article.body))
            self.assertIn('href="/web/content/42"', str(article.body))


@tagged('post_install', '-at_install')
class TestGuideVideoKnowledgeTour1660(Help1660Common):
    """The real public article page (needs website_knowledge: skipped where
    it is not installed, e.g. the addon CI)."""
    browser_size = '390x844'

    def setUp(self):
        super().setUp()
        module = self.env['ir.module.module'].sudo().search(
            [('name', '=', 'website_knowledge'), ('state', '=', 'installed')])
        if not module:
            raise unittest.SkipTest('website_knowledge is not installed')
        video, text = _guide_attachments(self.env)
        body = (
            f'<p>Guide</p>'
            f'<p><a class="o_fc_video" id="fc_vid_ok" href="/web/content/{video.id}">Voir la vidéo</a></p>'
            f'<p><a class="o_fc_video" id="fc_vid_text" href="/web/content/{text.id}">Notes</a></p>'
            f'<p><a class="o_fc_video" id="fc_vid_ext" '
            f'href="https://videos.example.com/web/content/{video.id}">Ailleurs</a></p>'
        )
        self.article = self.env['knowledge.article'].sudo().create({
            'name': 'Guide 1660', 'body': body, 'website_published': True})

    def test_public_article_logged_out(self):
        self.start_tour(f'/knowledge/article/{self.article.id}', 'sc_1660_knowledge_video')

    def test_public_article_portal_user(self):
        self.start_tour(
            f'/knowledge/article/{self.article.id}', 'sc_1660_knowledge_video',
            login='pc.tp@example.com')
