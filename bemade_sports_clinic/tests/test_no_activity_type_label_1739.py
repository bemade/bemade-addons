"""Task 1739 review (owner 2026-11-02) — every activity is a To-Do « À faire »
now, so the app shell no longer shows an activity's TYPE anywhere. Synthetic
fixtures only (this repository is public). The backend is untouched.

Acceptance criteria:

* UC-7a An activity card / row (sc_activity_row: /my/activities, a player's
  or a team's Activities tab) has no type label: no ``o_sc_activity_type``
  element and no type name in its head (title + subtitle), even when the
  activity has a summary and a (legacy, non-To-Do) type.
* UC-7b The activity details popout (/my/activity/<id>/popout) and the
  activity page (/my/activity/<id>) have no « Activity Type » line and do
  not print the type name.
* UC-7c In French, neither shows « Type d'activité ».
"""
from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_activity_cards_1736r1 import (
    ActivityCards1736r1Common,
)

# A distinctive type name, so its absence means something.
LEGACY_TYPE = 'Syn1739 legacy type'


class _NoTypeCommon(ActivityCards1736r1Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        legacy = cls.env['mail.activity.type'].create({'name': LEGACY_TYPE})
        (cls.act_player | cls.act_coach_created).write({'activity_type_id': legacy.id})

    @staticmethod
    def _flat(node):
        return ' '.join(node.text_content().split())

    def _popout_text(self, activity):
        resp = self.url_open('/my/activity/%s/popout' % activity.id)
        self.assertEqual(resp.status_code, 200)
        root = lxml_html.fromstring(resp.text).xpath('//*[@data-pk-section="activity.popout"]')
        self.assertTrue(root)
        return self._flat(root[0])

    def _page_read_text(self, activity):
        _text, page = self._get('/my/activity/%s' % activity.id)
        kv = page.xpath('//dl[contains(@class, "o_pk_kv")]')
        self.assertTrue(kv, 'the read view')
        return ' '.join(self._flat(dl) for dl in kv)


@tagged('post_install', '-at_install')
class TestNoActivityTypeLabel1739(_NoTypeCommon):

    def test_cards_have_no_type_label(self):
        self._switch(True)
        self._login('tp')
        for url in ('/my/activities',
                    '/my/player?player_id=%s&tab=activities' % self.player.id):
            _text, tree = self._get(url)
            card = self._card(tree, self.act_player)
            self.assertFalse(card.xpath('.//*[contains(@class, "o_sc_activity_type")]'), url)
            head = card.xpath('.//*[contains(@class, "o_sc_activity_head")]')[0]
            head_text = self._flat(head)
            self.assertIn(self.act_player.summary, head_text, url)
            self.assertNotIn(LEGACY_TYPE, head_text, url)

    def test_popout_and_page_have_no_type_line(self):
        self._switch(True)
        self._login('coach')
        text = self._popout_text(self.act_coach_created)
        self.assertIn('Due Date', text)
        self.assertNotIn('Activity Type', text)
        self.assertNotIn(LEGACY_TYPE, text)
        text = self._page_read_text(self.act_coach_created)
        self.assertIn('Due Date', text)
        self.assertNotIn('Activity Type', text)
        self.assertNotIn(LEGACY_TYPE, text)


@tagged('post_install', '-at_install')
class TestNoActivityTypeLabelFrench1739(_NoTypeCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.coach.write({'lang': 'fr_CA'})

    def test_french_no_type_line(self):
        self._switch(True)
        self._login('coach')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        for text in (self._popout_text(self.act_coach_created),
                     self._page_read_text(self.act_coach_created)):
            self.assertIn("Date d'échéance", text)
            self.assertNotIn("Type d'activité", text)
            self.assertNotIn(LEGACY_TYPE, text)
