"""Task 1586 — download an activity's attachments from the portal.
Synthetic fixtures only (invented file names and contents).

Acceptance criteria:

* UC-D1 A coach of the activity's player's team who can open the activity
  page (task 1589: it is assigned to them) GETs
  ``/my/activity/<activity>/attachment/<attachment>`` → 200 with
  the file's bytes, as a download (``Content-Disposition: attachment``).
* UC-D2 A coach of an unrelated team (cannot open the activity page) → 404,
  even with the exact URL — the URL grants nothing.
* UC-D3 An attachment of ANOTHER activity, or one not linked to any activity,
  requested under an activity the viewer can open → 404.
* UC-D4 An attachment linked through the activity's ``attachment_ids``
  (Many2many, not its res_model/res_id) → 200, and it is listed on the page.
* UC-D5 App shell (switch on): each attachment row is an
  ``<a href=".../attachment/<id>" download>`` link showing the file size.
* UC-D6 Switch off: the legacy detail page links to the same route (the
  former ``/web/content`` link 403'd for coaches).
* UC-D7 The view check is ONE helper (``_activity_view_access``) shared by
  the detail page and the download route (task 1589 changes it there).
* UC-D8 fr_CA (website-aware): the file size unit reads « Ko ».
* UC-D9 The size helper: bytes / KB / MB.
* UC-D10 (browser tour) the shell row's link answers the file.
"""
import base64

from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.controllers.app_shell import sc_file_size
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

PAYLOAD = b'synthetic attachment payload 1586 ' * 64  # 2176 bytes


class AttachmentDownloadCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        coach_g = env.ref('bemade_sports_clinic.group_portal_team_coach').id
        cls.other_coach = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'PC Other Coach', 'login': 'pc.other@example.com', 'password': 'pc-other',
            'group_ids': [Command.set([env.ref('base.group_portal').id, coach_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_b.id, 'partner_id': cls.other_coach.partner_id.id, 'role': 'coach',
        })
        # Task 1589: a coach opens only the activities assigned to / created
        # by them — the activity is the coach's (the TP still opens it: team
        # scope).
        cls.act_player.user_id = cls.coach
        Att = env['ir.attachment']
        cls.att = Att.create({
            'name': 'synthetic-plan.pdf', 'raw': PAYLOAD, 'mimetype': 'application/pdf',
            'res_model': 'mail.activity', 'res_id': cls.act_player.id,
        })
        # Linked to ANOTHER activity (the team one).
        cls.att_other = Att.create({
            'name': 'other-activity.txt', 'raw': b'other', 'res_model': 'mail.activity',
            'res_id': cls.act_team.id,
        })
        # Not linked to any activity.
        cls.att_loose = Att.create({'name': 'loose.txt', 'raw': b'loose'})
        # Linked via the activity's Many2many only.
        cls.att_m2m = Att.create({
            'name': 'm2m-note.txt', 'raw': b'm2m content', 'res_model': 'sports.patient',
            'res_id': cls.player.id,
        })
        cls.act_player.attachment_ids = [Command.link(cls.att_m2m.id)]

    def _url(self, att, activity=None):
        return '/my/activity/%s/attachment/%s' % ((activity or self.act_player).id, att.id)


@tagged('post_install', '-at_install')
class TestActivityAttachmentDownload(AttachmentDownloadCommon):

    # -- UC-D1 -----------------------------------------------------------
    def test_assignee_coach_downloads(self):
        self._login_coach()
        resp = self.url_open(self._url(self.att))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, PAYLOAD)
        self.assertIn('attachment', resp.headers.get('Content-Disposition', ''))
        self.assertIn('synthetic-plan.pdf', resp.headers.get('Content-Disposition', ''))

    def test_team_tp_downloads(self):
        self._login_tp()
        resp = self.url_open(self._url(self.att))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, PAYLOAD)

    # -- UC-D2 -----------------------------------------------------------
    @mute_logger('odoo.http', 'odoo.addons.base.models.ir_rule')
    def test_team_coach_not_assignee_404(self):
        """Task 1589: a coach of the team who neither is assigned to nor
        created the activity cannot open it, nor download its files."""
        self.act_player.user_id = self.tp
        self._login_coach()
        self.assertEqual(self.url_open('/my/activity/%s' % self.act_player.id).status_code, 404)
        resp = self.url_open(self._url(self.att))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn(PAYLOAD, resp.content)

    @mute_logger('odoo.http', 'odoo.addons.base.models.ir_rule')
    def test_unrelated_coach_404(self):
        self.authenticate('pc.other@example.com', 'pc-other')
        self.assertEqual(self.url_open('/my/activity/%s' % self.act_player.id).status_code, 404)
        resp = self.url_open(self._url(self.att))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn(PAYLOAD, resp.content)

    @mute_logger('odoo.http')
    def test_plain_portal_404(self):
        self._login_plain()
        resp = self.url_open(self._url(self.att))
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn(PAYLOAD, resp.content)

    @mute_logger('odoo.http')
    def test_missing_records_404(self):
        self._login_coach()
        self.assertEqual(self.url_open(self._url(self.att, self.act_player.browse(999999))).status_code, 404)
        self.assertEqual(self.url_open('/my/activity/%s/attachment/999999' % self.act_player.id).status_code, 404)

    # -- UC-D3 -----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_attachment_of_other_activity_404(self):
        self._login_tp()
        self.assertEqual(self.url_open(self._url(self.att_other)).status_code, 404)
        self.assertEqual(self.url_open(self._url(self.att_loose)).status_code, 404)

    # -- UC-D4 -----------------------------------------------------------
    def test_m2m_attachment(self):
        self._login_coach()
        resp = self.url_open(self._url(self.att_m2m))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b'm2m content')

    # -- UC-D5 -----------------------------------------------------------
    def test_shell_rows_are_download_links(self):
        self._switch(True)
        self._login_coach()
        _text, tree = self._get('/my/activity/%s' % self.act_player.id)
        self.assertIsNotNone(self._shell(tree))
        links = tree.xpath('//a[@data-sc-attachment]')
        hrefs = sorted(a.get('href') for a in links)
        self.assertEqual(hrefs, sorted([self._url(self.att), self._url(self.att_m2m)]))
        for a in links:
            self.assertIsNotNone(a.get('download'))
        row = tree.xpath('//a[@data-sc-attachment="%s"]' % self.att.id)[0]
        self.assertIn('synthetic-plan.pdf', row.text_content())
        self.assertIn('2.1 KB', row.text_content())

    # -- UC-D6 -----------------------------------------------------------
    def test_legacy_link_uses_route(self):
        self._login_coach()
        text, tree = self._get('/my/activity/%s' % self.act_player.id)
        self.assertIsNone(self._shell(tree))
        hrefs = tree.xpath('//a[contains(@href, "/attachment/")]/@href')
        self.assertIn(self._url(self.att), hrefs)
        self.assertNotIn('/web/content/%s' % self.att.id, text)

    # -- UC-D7 -----------------------------------------------------------
    def test_single_view_helper(self):
        from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import AccessControlMixin
        self.assertTrue(callable(getattr(AccessControlMixin, '_activity_view_access', None)))

    # -- UC-D9 -----------------------------------------------------------
    def test_size_helper(self):
        self.assertEqual(sc_file_size(512), '512 B')
        self.assertEqual(sc_file_size(2176), '2.1 KB')
        self.assertEqual(sc_file_size(3 * 1024 * 1024), '3.0 MB')
        self.assertEqual(sc_file_size(0), '0 B')


@tagged('post_install', '-at_install')
class TestActivityAttachmentDownloadFr(AttachmentDownloadCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.coach.write({'lang': 'fr_CA'})

    # -- UC-D8 -----------------------------------------------------------
    def test_fr_size_unit(self):
        self._switch(True)
        self._login_coach()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/activity/%s' % self.act_player.id)
        row = tree.xpath('//a[@data-sc-attachment="%s"]' % self.att.id)[0]
        self.assertIn('2,1 Ko', row.text_content())
        self.assertIn('Pièces jointes', ' '.join(tree.xpath('//section//text()')))


@tagged('post_install', '-at_install')
class TestActivityAttachmentTour(AttachmentDownloadCommon):
    """UC-D5 in a browser (static/tests/tours/sc_app_attachment_tours.js):
    the coach's row links to the route and following it answers the file."""
    browser_size = '390x844'

    def test_download_tour(self):
        self._switch(True)
        self.start_tour('/my/activity/%s' % self.act_player.id, 'sc_1586_attachment_download',
                        login='pc.coach@example.com')
