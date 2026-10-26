"""Task 1719 — the team announcement, compact (owner's layout B,
2026-10-26). Synthetic fixtures only.

Acceptance criteria:

* AC-1 No card and no head row: ONE title line — « Team announcement »,
  « History », and for an author the pencil (edit) and archive icon
  buttons (≥40×44 targets, 18 px glyphs).
* AC-2 Under it the megaphone beside the text; the text is clamped to 3
  lines (``data-sc-clamp="3"``) with « See more » (hidden until the text
  really overflows, browser) that expands it in place; one muted line
  « Until <date> » when there is a deadline.
* AC-3 A thin divider before the counters (CSS: the section's bottom
  border — browser).
* AC-4 Empty: an author gets a muted « No current announcement. » and the
  pencil opens the editor to add one (no « + Ajouter »); a coach / viewer
  with no announcement gets no section at all.
* AC-5 French: « Annonce d'équipe », « Historique », « Voir plus »,
  « Jusqu'au <date> », « Aucune annonce en cours. ».
* AC-6 Browser (phone 390 + laptop 1366): a long announcement shows « See
  more », which expands it; a short one shows none; the pencil of an empty
  announcement opens the compose form.
"""
from datetime import date

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

LONG = ('Synthetic practice moved to Thursday 6 pm at the synthetic arena. Bring training skates and a '
        'water bottle. Parents are invited to stay for the 7:15 meeting about the synthetic tournament '
        'schedule, the bus departure times and the equipment checklist for the whole weekend. ') * 4


class Announcement1719Common(AppShellCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)
        self.url = '/my/team?team_id=%s' % self.team_a.id

    def _area(self, tree):
        areas = tree.xpath('//section[@data-sc-section="team.announcement.area"]')
        return areas[0] if areas else None


@tagged('post_install', '-at_install')
class TestAnnouncementCompact1719(Announcement1719Common):

    def test_title_line(self):
        self.team_a.sudo().write({'announcement': 'Synthetic short note',
                                  'announcement_deadline': date(2030, 11, 2)})
        self._login_tp()
        _text, tree = self._get(self.url)
        area = self._area(tree)
        self.assertIsNotNone(area)
        self.assertEqual(area.get('data-sc-edit-card'), 'announcement')
        self.assertFalse(area.xpath('.//*[contains(concat(" ", @class, " "), " o_sc_card ")]'))
        self.assertFalse(area.xpath('.//*[contains(concat(" ", @class, " "), " o_sc_announcement_head ")]'))
        line = area.xpath('./div[contains(@class, "o_sc_announcement_titleline")]')
        self.assertEqual(len(line), 1)
        line = line[0]
        self.assertIn('Team announcement', line.text_content())
        self.assertTrue(line.xpath('.//button[@data-sc-sheet-open="sc_announcement_history_sheet"]'))
        self.assertEqual(len(line.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertEqual(len(line.xpath('.//form[@data-sc-section="team.announcement.archive"]//button')), 1)
        # The text: megaphone beside it, clamped, « See more » hidden by default.
        content = area.xpath('.//div[contains(@class, "o_sc_announcement_content")]')[0]
        self.assertTrue(content.xpath('./*[local-name()="svg" or contains(@class, "o_sc_icon")]'))
        body = content.xpath('.//p[contains(@class, "o_sc_announcement_body")]')[0]
        self.assertEqual(body.get('data-sc-clamp'), '3')
        self.assertEqual(body.text_content(), 'Synthetic short note')
        more = content.xpath('.//button[@data-sc-clamp-more]')[0]
        self.assertEqual(more.get('hidden'), 'hidden')
        self.assertEqual(' '.join(more.text_content().split()), 'See more')
        meta = content.xpath('.//*[@data-sc-clamp-meta]')[0]
        self.assertIsNone(meta.get('hidden'))
        meta_text = ' '.join(meta.text_content().split())
        self.assertTrue(meta_text.startswith('Until '), meta_text)
        self.assertIn('2030', meta_text)
        # No « Valid until: » label any more.
        self.assertNotIn('Valid until:', area.text_content())

    def test_no_deadline_meta_hidden(self):
        self.team_a.sudo().write({'announcement': LONG, 'announcement_deadline': False})
        self._login_coach()
        _text, tree = self._get(self.url)
        area = self._area(tree)
        self.assertIsNotNone(area)
        meta = area.xpath('.//*[@data-sc-clamp-meta]')[0]
        self.assertEqual(meta.get('hidden'), 'hidden')
        # A coach: no pencil, no archive.
        self.assertFalse(area.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(area.xpath('.//*[@data-sc-section="team.announcement.archive"]'))

    def test_empty_author_and_viewer(self):
        self.team_a.sudo().write({'announcement': False})
        self._login_tp()
        _text, tree = self._get(self.url)
        area = self._area(tree)
        self.assertIsNotNone(area)
        empty = area.xpath('.//p[contains(@class, "o_sc_announcement_empty")]')
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0].text_content().strip(), 'No current announcement.')
        self.assertIn('o_sc_muted', empty[0].get('class'))
        self.assertEqual(len(area.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertFalse(area.xpath('.//*[contains(@class, "o_sc_list_add")]'))
        self.assertTrue(area.xpath('.//*[@data-sc-section="team.announcement.edit"]'))
        self._login_coach()
        _text, tree = self._get(self.url)
        self.assertIsNone(self._area(tree))
        # The counters are still there.
        self.assertTrue(tree.xpath('//*[@data-sc-section="team.stats"]'))

    def test_french(self):
        env = self.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
                website.default_lang_id = fr_lang
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        self.tp.write({'lang': 'fr_CA'})
        self.team_a.sudo().write({'announcement': LONG, 'announcement_deadline': date(2030, 11, 2)})
        self._login_tp()
        _text, tree = self._get(self.url)
        area = self._area(tree)
        text = ' '.join(area.text_content().split())
        self.assertIn("Annonce d'équipe", text)
        self.assertIn('Historique', text)
        self.assertIn('Voir plus', text)
        self.assertIn("Jusqu'au", text)
        self.team_a.sudo().write({'announcement': False})
        _text, tree = self._get(self.url)
        self.assertIn('Aucune annonce en cours.', self._area(tree).text_content())


class _Tours1719:

    def test_see_more(self):
        self.team_a.sudo().write({'announcement': LONG, 'announcement_deadline': date(2030, 11, 2)})
        self.start_tour(self.url, 'sc_1719_see_more', login='pc.tp@example.com')

    def test_short_and_empty(self):
        self.team_a.sudo().write({'announcement': 'Synthetic short note', 'announcement_deadline': False})
        self.start_tour(self.url, 'sc_1719_short', login='pc.tp@example.com')
        self.team_a.sudo().write({'announcement': False})
        self.start_tour(self.url, 'sc_1719_empty_pencil', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestAnnouncementPhone1719(_Tours1719, Announcement1719Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestAnnouncementLaptop1719(_Tours1719, Announcement1719Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
