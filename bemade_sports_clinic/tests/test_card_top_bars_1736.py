"""Task 1736 — the app shell's card top bars, homogenised (owner-approved plan
2026-11-01). Synthetic fixtures only (this repository is public).

Use case: a therapist moves between cards (a player's header, injuries,
contacts, documents, timesheets, events, activities, quick notes, the team
announcement, the medical lists, the dashboard settings) and finds the
card's actions as icons, in the same place and order everywhere, coloured by
what they really do.

Acceptance criteria:

* AC-1 ONE icon group (``sc_card_icons``) per card top bar, left to right:
  ★ follow · clock + count · archive · trash · pencil (always rightmost).
* AC-2 The red trash (a permanent delete — notes, contacts, injuries,
  activities, medical items, dashboard sections) shows while the card is
  edited only (rendered hidden, ``data-sc-edit-only``) on a card with a
  pencil; it always asks first (a confirmation sheet / dialog). A card
  without a pencil (an activity row, a dashboard section, an archived quick
  note) shows it at once.
* AC-3 The archive icon (recoverable: timesheets, documents, quick notes,
  the team announcement) is visible in read mode, neutral, and its action is
  undone from the next page's toast (« … archived · Undo »); « Undo » puts
  the record back (same rights as the archive).
* AC-4 Event: « Activities » is the hero's clock with MY activities' count
  (the event row's count); no bottom « Activities » button. Task 1736 r1
  (owner 2026-11-01): cancelling an event is NOT an archive — « Cancel
  Event » stays its own red action (its reason sheet), « Restore event »
  its counterpart; no archive icon on the hero.
* AC-5 Injury card: the summary is the top bar — status pill, clock + count,
  the trash (« Delete injury », edit-only, for the Details group), the
  pencil (the Details group's, ``data-sc-edit-for``), then the chevron
  (``data-sc-injury-toggle``, the only fold control; the summary leaves the
  tab order). No bottom « Delete injury », no pencil in the Details head.
* AC-6 Player header: « Follow » is the ★ icon (aria-pressed = following)
  and the pencil sits in the same icon group, rightmost (no absolutely
  positioned pencil).
* AC-7 Activities: the delete is the red trash of the card's top bar, shown
  while editing (task 1736 r1: the cards have a pencil — see
  test_activity_cards_1736r1); « Done » is the LAST action on the card and
  on the detail page (no « Delete » in its bar).
* AC-8 fr_CA: the icons' names (Archiver, Supprimer, Modifier, Activités,
  Suivre) and the new texts render in French.
"""
from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.medical_common_1677 import set_medical
from odoo.addons.bemade_sports_clinic.tests.test_player_documents_manage_1432 import (
    PlayerDocuments1432Common,
)

ORDER = ('o_sc_follow', 'o_sc_card_clock', 'o_sc_card_archive', 'o_sc_card_trash', 'o_sc_card_edit')


class TopBars1736Common(PlayerDocuments1432Common):

    def setUp(self):
        super().setUp()
        set_medical(self.player, allergies=[('Synthetic kiwi', False)], conditions=[],
                    epipen=False, none_allergy=False, none_condition=False)
        self.qnote = self.env['sports.quick.note'].create({
            'note': 'SC1736 synthetic jot', 'user_id': self.tp.id,
        })

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _icons(node):
        """The icon group's controls, as their ORDER kind (others ignored)."""
        groups = node.xpath('.//*[@data-sc-card-icons]')
        if not groups:
            return []
        kinds = []
        for el in groups[0].iter():
            classes = (el.get('class') or '').split()
            kinds += [kind for kind in ORDER if kind in classes and el.tag in ('a', 'button')]
        return kinds

    def _assert_order(self, node, expected):
        kinds = self._icons(node)
        self.assertEqual(kinds, list(expected))
        self.assertEqual(kinds, sorted(kinds, key=ORDER.index), 'the shared order')

    @staticmethod
    def _one(node, xpath):
        found = node.xpath(xpath)
        assert len(found) == 1, (xpath, len(found))
        return found[0]

    def _post(self, url, **data):
        data['csrf_token'] = self._csrf()
        return self.url_open(url, data=data, allow_redirects=False)

    def _player_url(self, tab='overview'):
        return '/my/player?player_id=%s&team_id=%s&tab=%s' % (self.player.id, self.team_a.id, tab)


@tagged('post_install', '-at_install')
class TestCardTopBars1736(TopBars1736Common):

    # -- AC-1 / AC-6: player header ----------------------------------------
    def test_player_hero_star_and_pencil(self):
        self._login_tp()
        _text, tree = self._get(self._player_url())
        hero = self._one(tree, '//*[@data-sc-section="player.hero"]')
        self._assert_order(hero, ('o_sc_follow', 'o_sc_card_edit'))
        star = self._one(hero, './/button[@data-sc-follow]')
        self.assertIn('o_sc_icon_btn', star.get('class'))
        self.assertEqual(star.get('aria-pressed'), 'false')
        self.assertEqual(star.get('aria-label'), 'Follow')
        self.assertFalse(star.text_content().strip(), 'an icon, no text')
        self.assertFalse(hero.xpath('.//*[contains(@class, "o_sc_hero_edit_toggle")]'))
        # Following: pressed, « Unfollow » as its title.
        self._post('/my/player/%s/follow' % self.player.id, follow='1')
        _text, tree = self._get(self._player_url())
        star = self._one(tree, '//*[@data-sc-section="player.hero"]//button[@data-sc-follow]')
        self.assertEqual(star.get('aria-pressed'), 'true')
        self.assertEqual(star.get('title'), 'Unfollow')

    # -- AC-2 / AC-5: injury card -------------------------------------------
    def test_injury_card_top_bar(self):
        self._login_tp()
        _text, tree = self._get(self._player_url('injuries'))
        card = self._one(tree, '//details[@id="injury-%s"]' % self.injury.id)
        summary = self._one(card, './summary')
        self.assertEqual(summary.get('tabindex'), '-1')
        self.assertFalse(summary.get('data-sc-fragment'), 'the icons are outside the fragment')
        self.assertTrue(summary.xpath('./*[@data-sc-fragment="sports.patient.injury:%s:summary"]'
                                      % self.injury.id))
        # act_injury is the therapist's: clock with 1.
        self._assert_order(summary, ('o_sc_card_clock', 'o_sc_card_trash', 'o_sc_card_edit'))
        clock = self._one(summary, './/a[contains(@class, "o_sc_card_clock")]')
        self.assertEqual(clock.get('data-sc-activity-clock'), '1')
        trash = self._one(summary, './/button[contains(@class, "o_sc_card_trash")]')
        self.assertEqual(trash.get('hidden'), 'hidden')
        self.assertEqual(trash.get('data-sc-edit-only'), '1')
        self.assertEqual(trash.get('data-sc-edit-for'), 'injury-details')
        self.assertEqual(trash.get('data-sc-sheet-open'), 'sc_delete_injury_sheet_%s' % self.injury.id)
        self.assertIn('o_sc_icon_btn_danger', trash.get('class'))
        self.assertTrue(tree.xpath('//dialog[@id="sc_delete_injury_sheet_%s"]' % self.injury.id))
        pencil = self._one(summary, './/button[@data-sc-edit-toggle]')
        self.assertEqual(pencil.get('data-sc-edit-for'), 'injury-details')
        # The chevron after the icon group, the only fold control.
        chevron = self._one(summary, './/button[@data-sc-injury-toggle]')
        self.assertEqual(chevron.get('aria-controls'), 'injury-%s-body' % self.injury.id)
        self.assertTrue(card.xpath('.//*[@id="injury-%s-body"]' % self.injury.id))
        # The status pill stays in the summary; the Details group has no
        # pencil of its own; no bottom « Delete injury ».
        self.assertTrue(summary.xpath('.//*[@data-sc-pill-key="stage"]'))
        details = self._one(card, './/*[@data-sc-edit-card="injury-details"]')
        self.assertFalse(details.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(card.xpath('.//*[contains(@class, "o_sc_injury_card_actions")]'))
        self.assertEqual(len(card.xpath('.//*[@data-sc-action="injury.delete"]')), 1)

    def test_injury_card_coach_no_trash(self):
        self._login_coach()
        _text, tree = self._get(self._player_url('injuries'))
        card = self._one(tree, '//details[@id="injury-%s"]' % self.injury.id)
        self.assertNotIn('o_sc_card_trash', self._icons(card.xpath('./summary')[0]))

    # -- AC-2: emergency contact ----------------------------------------------
    def test_contact_trash_edit_only(self):
        self._login_tp()
        _text, tree = self._get(self._player_url('info'))
        card = self._one(tree, '//section[@data-sc-contact-id="%s"]' % self.contact.id)
        self._assert_order(card, ('o_sc_card_trash', 'o_sc_card_edit'))
        trash = self._one(card, './/button[contains(@class, "o_sc_card_trash")]')
        self.assertEqual(trash.get('hidden'), 'hidden')
        self.assertEqual(trash.get('data-sc-sheet-open'), 'sc_delete_contact_%s' % self.contact.id)
        # No « Delete » text button left in the edit view.
        edit = self._one(card, './/*[@data-sc-edit-view="edit"]')
        self.assertFalse(edit.xpath('.//button[@data-sc-action="contact.delete"]'))
        self.assertTrue(edit.xpath('.//button[@data-sc-edit-done]'))
        # A coach edits but never deletes.
        self._login_coach()
        _text, tree = self._get(self._player_url('info'))
        card = self._one(tree, '//section[@data-sc-contact-id="%s"]' % self.contact.id)
        self._assert_order(card, ('o_sc_card_edit',))

    # -- AC-2: medical list item ----------------------------------------------
    def test_medical_item_trash(self):
        self._login_tp()
        _text, tree = self._get(self._player_url('injuries'))
        sheet = self._one(tree, '//dialog[@id="sc_med_player_allergy_%s"]' % self.player.id)
        card = sheet.xpath('.//li[@data-sc-med-item]')[0]
        self._assert_order(card, ('o_sc_card_trash', 'o_sc_card_edit'))
        trash = self._one(card, './/button[@data-sc-med-item-delete]')
        self.assertEqual(trash.get('hidden'), 'hidden')
        self.assertEqual(trash.get('data-sc-edit-only'), '1')

    # -- AC-3: documents ------------------------------------------------------
    def test_document_archive_icon_and_undo(self):
        self.tp.write({'lang': 'en_US'})
        self._login_tp()
        _text, tree = self._get(self._tab_url())
        item = self._tab_item(tree, self.doc_player)
        self._assert_order(item, ('o_sc_card_archive', 'o_sc_card_edit'))
        archive = self._one(item, './/button[contains(@class, "o_sc_card_archive")]')
        self.assertIsNone(archive.get('hidden'), 'visible in read mode')
        self.assertNotIn('o_sc_icon_btn_danger', archive.get('class'))
        form = archive.getparent()
        self.assertEqual(form.get('action'), '/my/injury/document/delete/%s' % self.doc_player.id)
        self.assertEqual(form.xpath('./input[@name="sc_undo"]/@value'), ['1'])
        self.assertFalse(tree.xpath('//dialog[@id="sc_delete_player_document_%s"]' % self.doc_player.id),
                         'no confirmation: an undo instead')
        # Archive: back without the banner, the toast offers « Undo ».
        back = self._tab_url()
        resp = self._post('/my/injury/document/delete/%s' % self.doc_player.id,
                          return_url=back, sc_undo='1')
        self.assertIn(resp.status_code, (302, 303))
        self.assertNotIn('success=', resp.headers['Location'])
        self.assertFalse(self._alive(self.doc_player))
        text, tree = self._get(resp.headers['Location'])
        self.assertNotIn('Document deleted.', text)
        toast = self._one(tree, '//*[contains(@class, "o_sc_toast")]')
        self.assertEqual(toast.get('data-sc-notify'), 'Document archived.')
        undo = self._one(tree, '//form[@data-sc-form="sc.undo"]')
        self.assertTrue(undo.get('action').startswith('/my/injury/document/restore/%s' % self.doc_player.id))
        self.assertEqual(undo.get('data-sc-toast-action'), 'Undo')
        # Shown once.
        _text, tree = self._get(self._tab_url())
        self.assertFalse(tree.xpath('//form[@data-sc-form="sc.undo"]'))
        # Undo: back in the list, with a chatter note.
        Message = self.env['mail.message']
        before = Message.search([('model', '=', 'sports.patient'), ('res_id', '=', self.player.id)])
        resp = self._post(undo.get('action'))
        self.assertIn(resp.status_code, (302, 303))
        self.assertEqual(resp.headers['Location'].split('://', 1)[-1].split('/', 1)[-1], back.lstrip('/'))
        self.assertTrue(self._alive(self.doc_player))
        notes = Message.search([('model', '=', 'sports.patient'), ('res_id', '=', self.player.id)]) - before
        self.assertIn('restored by %s' % self.tp.name, notes.body)

    def test_document_restore_refused_to_other_therapist(self):
        self.doc_player._sc_portal_archive(self.tp)
        self._login_tp2()
        resp = self._post('/my/injury/document/restore/%s' % self.doc_player.id)
        self.assertIn(resp.status_code, (302, 303))
        self.assertIn('error=permission_denied', resp.headers['Location'])
        self.assertFalse(self._alive(self.doc_player))

    # -- AC-3: timesheets -----------------------------------------------------
    def test_timesheet_archive_icon_and_undo(self):
        self._login_tp()
        url = '/my/event/%s' % self.event.id
        _text, tree = self._get(url)
        card = self._one(tree, '//article[@data-sc-timesheet-id="%s"]' % self.timesheet.id)
        self._assert_order(card, ('o_sc_card_archive', 'o_sc_card_edit'))
        archive = self._one(card, './/button[contains(@class, "o_sc_card_archive")]')
        self.assertIsNone(archive.get('hidden'))
        self.assertEqual(archive.get('type'), 'submit')
        form = self._one(tree, '//form[@id="%s"]' % archive.get('form'))
        self.assertEqual(form.get('action'), '/my/sc/timesheet/%s/delete' % self.timesheet.id)
        self.assertEqual(form.xpath('./input[@name="sc_undo"]/@value'), ['1'])
        # The state chip sits first in the group; no bottom « Delete ».
        self.assertTrue(card.xpath('.//*[@data-sc-card-icons]/span[@data-sc-ts-state]'))
        self.assertFalse(card.xpath('.//*[contains(@class, "o_sc_card_actions")]'))
        self.assertFalse(tree.xpath('//dialog[starts-with(@id, "sc_ts_delete_")]'))
        resp = self._post(form.get('action'), return_url=url, sc_undo='1')
        self.assertEqual(resp.headers['Location'].rsplit(url, 1)[-1], '')
        self.timesheet.invalidate_recordset()
        self.assertFalse(self.timesheet.active)
        _text, tree = self._get(url)
        self.assertEqual(self._one(tree, '//*[contains(@class, "o_sc_toast")]').get('data-sc-notify'),
                         'Timesheet archived.')
        undo = self._one(tree, '//form[@data-sc-form="sc.undo"]')
        resp = self._post(undo.get('action'))
        self.assertTrue(resp.headers['Location'].endswith(url))
        self.timesheet.invalidate_recordset()
        self.assertTrue(self.timesheet.active)

    def test_timesheet_restore_refused_to_others(self):
        self.timesheet.with_user(self.tp).action_soft_delete()
        self._login_tp2()
        with self.assertLogs('odoo.http', level='WARNING'):
            resp = self._post('/my/sc/timesheet/%s/restore' % self.timesheet.id)
        self.assertNotIn(resp.status_code, (302, 303))
        self.timesheet.invalidate_recordset()
        self.assertFalse(self.timesheet.with_context(active_test=False).active)

    # -- AC-2 / AC-3: quick notes ---------------------------------------------
    def test_quick_note_archive_trash(self):
        self._login_tp()
        _text, tree = self._get('/my/notepad')
        card = self._one(tree, '//article[@data-sc-quick-note-id="%s"]' % self.qnote.id)
        self._assert_order(card, ('o_sc_card_archive', 'o_sc_card_trash', 'o_sc_card_edit'))
        trash = self._one(card, './/button[contains(@class, "o_sc_card_trash")]')
        self.assertEqual(trash.get('hidden'), 'hidden')
        self.assertEqual(trash.get('data-sc-sheet-open'), 'sc_qn_delete_%s' % self.qnote.id)
        self.assertTrue(tree.xpath('//dialog[@id="sc_qn_delete_%s"]' % self.qnote.id))
        self.assertFalse(card.xpath('.//*[contains(@class, "o_sc_card_actions")]'))
        form = self._one(card, './/form[.//button[contains(@class, "o_sc_card_archive")]]')
        self.assertEqual(form.get('action'), '/my/notepad/%s/archive' % self.qnote.id)
        resp = self._post(form.get('action'), sc_undo='1')
        self.assertNotIn('success=', resp.headers['Location'])
        self.qnote.invalidate_recordset()
        self.assertFalse(self.qnote.active)
        _text, tree = self._get('/my/notepad')
        undo = self._one(tree, '//form[@data-sc-form="sc.undo"]')
        self.assertEqual(undo.get('action'), '/my/notepad/%s/restore?undo=1' % self.qnote.id)
        resp = self._post(undo.get('action'))
        self.assertIn('/my/notepad?success=note_restored#note-%s' % self.qnote.id, resp.headers['Location'])
        self.qnote.invalidate_recordset()
        self.assertTrue(self.qnote.active)
        # An archived note: no pencil, so its trash shows; « Restore » stays.
        self.qnote.active = False
        _text, tree = self._get('/my/notepad?show_archived=1')
        card = self._one(tree, '//article[@data-sc-quick-note-id="%s"]' % self.qnote.id)
        self._assert_order(card, ('o_sc_card_trash',))
        self.assertIsNone(self._one(card, './/button[contains(@class, "o_sc_card_trash")]').get('hidden'))
        self.assertTrue(card.xpath('.//button[@data-sc-action="note.restore"]'))

    # -- AC-4: event hero -----------------------------------------------------
    def test_event_hero_top_bar(self):
        self._login_tp()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        hero = self._one(tree, '//section[@data-sc-section="event.hero"]')
        # Task 1736 r1 (deliberate update): no archive icon — « Cancel Event »
        # is its own red action again (below the hero's details).
        self._assert_order(hero, ('o_sc_card_clock', 'o_sc_card_edit'))
        clock = self._one(hero, './/a[contains(@class, "o_sc_card_clock")]')
        self.assertEqual(clock.get('href'), '/my/event/activities?event_id=%s' % self.event.id)
        # act_event: the therapist's — the same count as the event's row.
        self.assertEqual(clock.get('data-sc-activity-clock'), '1')
        self.assertEqual(clock.xpath('./span[contains(@class, "o_sc_card_badge")]/text()'), ['1'])
        self.assertFalse(hero.xpath('.//*[contains(@class, "o_sc_card_archive")]'))
        cancel = self._one(hero, './/*[contains(@class, "o_sc_actions_row")]/button[@data-sc-action="event.cancel"]')
        self.assertEqual(cancel.get('data-sc-sheet-open'), 'sc_event_cancel_sheet')
        self.assertIn('o_sc_btn_danger', cancel.get('class'))
        self.assertEqual(cancel.text_content().strip(), 'Cancel Event')
        self.assertTrue(tree.xpath('//dialog[@id="sc_event_cancel_sheet"]'))
        # Only « Cancel Event » in that row (« Activities » is the clock).
        self.assertEqual(hero.xpath('.//*[contains(@class, "o_sc_actions_row")]//@data-sc-action'), ['event.cancel'])
        # Its sheet posts the cancel itself — no archive « Undo » toast.
        form = self._one(tree, '//dialog[@id="sc_event_cancel_sheet"]//form')
        self.assertEqual(form.get('action'), '/my/event/%s/cancel' % self.event.id)
        self.assertFalse(form.xpath('.//input[@name="sc_undo"]'))
        # No activity of mine: the clock still leads to them, without a badge.
        self.act_event.unlink()
        _text, tree = self._get('/my/event/%s' % self.event.id)
        clock = self._one(tree, '//section[@data-sc-section="event.hero"]//a[contains(@class, "o_sc_card_clock")]')
        self.assertEqual(clock.get('data-sc-activity-clock'), '0')
        self.assertFalse(clock.xpath('./span[contains(@class, "o_sc_card_badge")]'))
        # Cancelled: « Restore event » (its counterpart), no « Cancel Event ».
        self.event.sudo().write({'state': 'cancelled'})
        _text, tree = self._get('/my/event/%s' % self.event.id)
        hero = self._one(tree, '//section[@data-sc-section="event.hero"]')
        self.assertNotIn('o_sc_card_archive', self._icons(hero))
        self.assertTrue(hero.xpath('.//button[@data-sc-action="event.restore"]'))
        self.assertFalse(hero.xpath('.//button[@data-sc-action="event.cancel"]'))

    # -- AC-7: activities -----------------------------------------------------
    def test_activity_row_and_detail(self):
        self._login_tp()
        _text, tree = self._get('/my/activities')
        # (an activity may be listed in more than one group: the first)
        row = tree.xpath('//*[@data-sc-activity-row="%s"]' % self.act_team.id)[0]
        # Task 1736 r1 (deliberate update): the card has a pencil — the
        # trash shows while editing only.
        self._assert_order(row, ('o_sc_card_trash', 'o_sc_card_edit'))
        trash = self._one(row, './/button[contains(@class, "o_sc_card_trash")]')
        self.assertEqual(trash.get('hidden'), 'hidden')
        self.assertEqual(trash.get('data-sc-edit-only'), '1')
        self.assertEqual(trash.get('data-sc-activity-id'), str(self.act_team.id))
        self.assertEqual(trash.get('data-sc-sheet-open'), 'sc_activity_cancel_sheet')
        actions = row.xpath('.//*[contains(@class, "o_sc_activity_actions")]/button/@data-sc-action')
        self.assertEqual(actions[-1], 'activity.complete')
        self.assertNotIn('activity.cancel', actions)
        _text, tree = self._get('/my/activity/%s' % self.act_team.id)
        card = self._one(tree, '//section[@data-sc-section="activity.detail"]')
        self._assert_order(card, ('o_sc_card_trash', 'o_sc_card_edit'))
        self.assertEqual(self._one(card, './/button[contains(@class, "o_sc_card_trash")]').get('hidden'), 'hidden')
        bar = tree.xpath('//*[contains(@class, "o_sc_actionbar")]/button/@data-sc-action')
        self.assertEqual(bar[-1], 'activity.complete')
        self.assertNotIn('activity.cancel', bar)

    # -- AC-1 / AC-3: team announcement ---------------------------------------
    def test_announcement_archive_before_pencil(self):
        self.team_a.sudo().write({'announcement': 'SC1736 synthetic announcement'})
        self._login_tp()
        _text, tree = self._get('/my/team?team_id=%s' % self.team_a.id)
        area = self._one(tree, '//section[@data-sc-section="team.announcement.area"]')
        self._assert_order(area, ('o_sc_card_archive', 'o_sc_card_edit'))
        self.assertTrue(area.xpath('.//form[@data-sc-section="team.announcement.archive"]'))

    # -- AC-2: dashboard sections ---------------------------------------------
    def test_dashboard_remove_is_trash_with_confirm(self):
        self._login_tp()
        _text, tree = self._get('/my/app/dashboard/configure')
        # The default sections cannot be removed: no trash.
        self.assertFalse(tree.xpath('//button[@data-sc-dash-remove]'))
        # An added (second) section can.
        widget = tree.xpath('//select[@id="sc_dash_add_widget"]/option/@value')[0]
        self._post('/my/app/dashboard/configure/add', widget=widget)
        _text, tree = self._get('/my/app/dashboard/configure')
        items = tree.xpath('//li[@data-sc-dash-item]')
        removable = [item for item in items if item.xpath('.//button[@data-sc-dash-remove]')]
        self.assertEqual(len(removable), 1)
        for item in removable:
            self._assert_order(item, ('o_sc_card_trash',))
            trash = self._one(item, './/button[@data-sc-dash-remove]')
            self.assertIn('o_sc_icon_btn_danger', trash.get('class'))
            self.assertIsNone(trash.get('hidden'))
            self.assertEqual(trash.get('type'), 'submit')
            form = self._one(tree, '//form[@id="%s"]' % trash.get('form'))
            self.assertEqual(form.get('action'), '/my/app/dashboard/configure/remove')
            self.assertEqual(form.get('data-sc-dash-remove-form'), '1')
            self.assertEqual(form.get('data-sc-confirm-title'), 'Remove this section?')
            self.assertTrue(form.get('data-sc-confirm-ok'))
            # The item's top bar: its own icon group, after the head.
            self.assertEqual(trash.getparent().getparent(), item)


@tagged('post_install', '-at_install')
class TestCardTopBarsI18n1736(TopBars1736Common):
    """AC-8 — website-aware (the project CI installs website)."""

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
        cls.tp.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        return self._get(url)

    def test_icon_names_in_french(self):
        _text, tree = self._fr('/my/notepad')
        card = self._one(tree, '//article[@data-sc-quick-note-id="%s"]' % self.qnote.id)
        icons = card.xpath('.//*[@data-sc-card-icons]')[0]
        labels = [b.get('aria-label') for b in icons.xpath('.//button')]
        self.assertEqual(labels, ['Archiver', 'Supprimer', 'Modifier'])
        _text, tree = self._fr('/my/event/%s' % self.event.id)
        hero = self._one(tree, '//section[@data-sc-section="event.hero"]')
        self.assertEqual(self._one(hero, './/a[contains(@class, "o_sc_card_clock")]').get('aria-label'),
                         'Mes activités : 1')
        # Task 1736 r1 (deliberate update): its own red button again.
        self.assertEqual(self._one(hero, './/button[@data-sc-action="event.cancel"]').text_content().strip(),
                         "Annuler l'événement")
        _text, tree = self._fr(self._player_url('injuries'))
        hero = self._one(tree, '//*[@data-sc-section="player.hero"]')
        self.assertEqual(self._one(hero, './/button[@data-sc-follow]').get('aria-label'), 'Suivre')
        card = self._one(tree, '//details[@id="injury-%s"]' % self.injury.id)
        self.assertEqual(self._one(card, './/button[contains(@class, "o_sc_card_trash")]').get('aria-label'),
                         'Supprimer la blessure')
        self.assertEqual(self._one(card, './/button[@data-sc-injury-toggle]').get('aria-label'),
                         'Afficher ou masquer la blessure')
        _text, tree = self._fr('/my/app/dashboard/configure')
        widget = tree.xpath('//select[@id="sc_dash_add_widget"]/option/@value')[0]
        self._post('/my/app/dashboard/configure/add', widget=widget)
        _text, tree = self._get('/my/app/dashboard/configure')
        form = tree.xpath('//form[@data-sc-dash-remove-form]')[0]
        self.assertEqual(form.get('data-sc-confirm-title'), 'Retirer cette section ?')

    def test_undo_toast_in_french(self):
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        self._post('/my/notepad/%s/archive' % self.qnote.id, sc_undo='1')
        _text, tree = self._get('/my/notepad')
        self.assertEqual(self._one(tree, '//*[contains(@class, "o_sc_toast")]').get('data-sc-notify'),
                         'Note archivée.')
        self.assertEqual(self._one(tree, '//form[@data-sc-form="sc.undo"]').get('data-sc-toast-action'),
                         'Annuler')
