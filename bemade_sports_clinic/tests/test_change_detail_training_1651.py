"""Task 1651 — the recent-changes detail shows the training recommendation
like the other player cards (one shared head). Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 For one synthetic player, the expanded recent-changes detail
  (/my/player/<id>/recent-changes?detail=1) and the row detail
  (/my/player/<id>/row-detail) both carry
  ``.o_sc_row_detail_training > h3.o_sc_change_detail_sub``, the text and the
  « Updated on … » stamp ([data-sc-change-detail-stamp]); no fa-heartbeat in
  the change detail.
* UC-2 fr_CA: « Recommandation d'entraînement » renders in the change detail.
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _text(node):
    return ' '.join(node.text_content().split())


@tagged('post_install', '-at_install')
class TestChangeDetailTraining1651(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player.write({'training_recommendation': 'Synthetic bike only\nSecond line'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _detail(self, url):
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text, lxml_html.fromstring('<div>%s</div>' % resp.text)

    def test_both_details_share_the_head(self):
        self._login_tp()
        for url in ('/my/player/%s/recent-changes?detail=1' % self.player.id,
                    '/my/player/%s/row-detail' % self.player.id):
            text, tree = self._detail(url)
            block = tree.xpath('//*[contains(@class, "o_sc_row_detail_training")]')
            self.assertEqual(len(block), 1, url)
            self.assertTrue(block[0].xpath('./h3[contains(@class, "o_sc_change_detail_sub")]'), url)
            self.assertIn('Second line', _text(block[0]), url)
            if self.player.last_training_recommendation_info:
                self.assertTrue(block[0].xpath('.//*[@data-sc-change-detail-stamp]'), url)
            self.assertNotIn('fa-heartbeat', text, url)

    def test_change_detail_in_french(self):
        self.env['res.lang']._activate_lang('fr_CA')
        self.env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if self.env['ir.module.module']._get('website').state == 'installed':
            fr = self.env['res.lang']._lang_get('fr_CA')
            for website in self.env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr.id)]
        self.tp.write({'lang': 'fr_CA'})
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        text, _tree = self._detail('/my/player/%s/recent-changes?detail=1' % self.player.id)
        self.assertIn("Recommandation d", text.replace('&#39;', "'"))
