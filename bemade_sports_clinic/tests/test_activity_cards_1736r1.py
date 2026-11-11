"""Task 1736 review round 1 (owner 2026-11-01) — activity cards edited in
place, their details popout, and the event's « Cancel Event » (not an
archive). Synthetic fixtures only (this repository is public).

Use case: a therapist (or a coach, on their own activities) works through
their activities — /my/activities, a team's or a player's Activities tab,
the dashboard's « À faire » — and changes one where it is listed, like any
other card: the pencil turns the card into its edit view (summary, due
date, assignee, note; saved as they go), the red trash shows while editing
(it asks first), « Done » stays the last action. A tap on the card shows
its details in a popout; the activity page stays for deep links.

Acceptance criteria:

* AC-1 Every activity card (sc_activity_row) of a user who may act on the
  activity (``_activity_act_access``) is an edit card: pencil rightmost in
  its top bar, the trash before it, rendered hidden and edit-only; its edit
  view holds the autosave fields summary, due date, assignee (only where
  the user may reassign — ``activities.reassign`` — with the same choices
  as the detail page: the per-actor assignable users + the current
  assignee) and note, inside an inert ``<template data-sc-lazy-edit>``
  (mounted on the first pencil tap). No activity type field (read-only, as
  on the detail page).
* AC-2 No « Reschedule » / « Reassign » buttons or sheets anywhere in the
  shell (cards, detail page); « Done » is the card's only footer action and
  the detail bar's only action.
* AC-3 A user who may open but not act gets no pencil, no trash, no Done,
  no edit fields.
* AC-4 The inline fields save through /my/app/save (date, assignee, note):
  allowed for an actor, refused for anyone else (403 / 404) and for an
  assignee outside the user's list (400, nothing written).
* AC-5 /my/activities lists an activity in « All » and in its state's tab:
  the field ids stay unique on the page.
* AC-6 A tap on the card opens the details popout: the card's main link
  keeps ``/my/activity/<id>`` (new tab, no JS) and carries
  ``data-sc-sheet-open="sc_activity_detail_sheet"`` +
  ``data-sc-sheet-url="/my/activity/<id>/popout"``; the sheet is on every
  page listing cards (dashboard included).
* AC-7 /my/activity/<id>/popout answers the read-only details (summary,
  type, due date, assignee, related record link, created on / by, note,
  attachments, the state chip), no edit control; 404 for whoever may not
  open the activity.
* AC-8 Deep link: /my/activity/<id> still renders the page (its pencil card
  shows the same details, « Created by » included).
* AC-9 Event hero: « Cancel Event » is a red action button (its reason
  sheet), not an archive icon; « Restore event » is its counterpart.
* AC-10 fr_CA: « Créé par », the popout's « Activité », the card's « Done »
  reads « Terminé » (as on the detail page; it read « Fait »).
"""
import json

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_activity_permissions_1589 import (
    ActivityPermissionsCommon,
)

FIELDS = ('summary', 'date_deadline', 'user_id', 'note')


class ActivityCards1736r1Common(ActivityPermissionsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.act_player.write({'note': '<p>SC1736r1 synthetic note</p>'})

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _card(tree, activity):
        cards = tree.xpath('//*[@data-sc-activity-row="%s"]' % activity.id)
        assert cards, 'no card for %s' % activity.id
        return cards[0]

    @staticmethod
    def _props(node):
        return [json.loads(p) for p in node.xpath('.//owl-component/@props')]

    @staticmethod
    def _icons(card):
        group = card.xpath('.//*[@data-sc-card-icons]')[0]
        kinds = []
        for el in group.iter('button', 'a'):
            classes = (el.get('class') or '').split()
            kinds += [k for k in ('o_pk_card_trash', 'o_pk_card_edit') if k in classes]
        return kinds


@tagged('post_install', '-at_install')
class TestActivityCards1736r1(ActivityCards1736r1Common):

    # -- AC-1 / AC-2 -------------------------------------------------------
    def test_card_is_an_edit_card(self):
        self._switch(True)
        self._login('tp')
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        card = self._card(tree, self.act_player)
        self.assertIn('o_pk_edit_card', card.get('class'))
        self.assertEqual(card.get('data-pk-edit-card'), 'activity-%s' % self.act_player.id)
        self.assertEqual(self._icons(card), ['o_pk_card_trash', 'o_pk_card_edit'])
        trash = card.xpath('.//button[contains(@class, "o_pk_card_trash")]')[0]
        self.assertEqual(trash.get('hidden'), 'hidden')
        self.assertEqual(trash.get('data-sc-edit-only'), '1')
        self.assertEqual(trash.get('data-sc-sheet-open'), 'sc_activity_cancel_sheet')
        self.assertEqual(trash.get('data-sc-activity-id'), str(self.act_player.id))
        self.assertTrue(tree.xpath('//dialog[@id="sc_activity_cancel_sheet"]'))
        pencil = card.xpath('.//button[contains(@class, "o_pk_card_edit")]')[0]
        self.assertEqual(pencil.get('data-sc-edit-toggle'), '1')
        self.assertEqual(pencil.get('data-sc-action'), 'activity.edit')
        # The edit view: hidden, its fields inside the inert lazy template.
        edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden')
        self.assertEqual(edit.get('data-sc-lazy-edit-host'), '1')
        template = edit.xpath('./template[@data-sc-lazy-edit]')
        self.assertEqual(len(template), 1)
        props = self._props(template[0])
        self.assertEqual([p['field'] for p in props], list(FIELDS))
        self.assertTrue(all(p['model'] == 'mail.activity' and p['recordId'] == self.act_player.id
                            for p in props))
        by_field = {p['field']: p for p in props}
        self.assertEqual(by_field['date_deadline']['inputType'], 'date')
        self.assertEqual(by_field['note']['value'], 'SC1736r1 synthetic note')
        self.assertTrue(by_field['note'].get('clearable'))
        options = [str(o[0]) for o in by_field['user_id']['options']]
        # The detail page's choices: the per-actor list + the assignee.
        _text, page = self._get('/my/activity/%s' % self.act_player.id)
        page_props = self._props(page.xpath('//*[@data-pk-edit-card="activity"]')[0])
        page_options = [str(o[0]) for o in
                        [p for p in page_props if p['field'] == 'user_id'][0]['options']]
        self.assertEqual(options, page_options)
        self.assertIn(str(self.coach.id), options)
        # No activity type field (read-only, as on the detail page).
        self.assertNotIn('activity_type_id', by_field)
        # AC-2: « Done » is the only footer action, no Reschedule / Reassign.
        actions = card.xpath('.//*[contains(@class, "o_sc_activity_actions")]//@data-sc-action')
        self.assertEqual(actions, ['activity.complete'])
        self.assertFalse(tree.xpath('//*[@data-sc-action="activity.reschedule" or '
                                    '@data-sc-action="activity.reassign"]'))
        self.assertFalse(tree.xpath('//dialog[@id="sc_activity_reschedule_sheet" or '
                                    '@id="sc_activity_reassign_sheet"]'))

    def test_every_list_has_editable_cards(self):
        """Team / event Activities, /my/activities and the dashboard to-do."""
        self._switch(True)
        self._login('tp')
        for url, activity in (
                ('/my/team/activities?team_id=%s' % self.team_a.id, self.act_team),
                ('/my/event/activities?event_id=%s' % self.event.id, self.act_event),
                ('/my/activities', self.act_injury)):
            _text, tree = self._get(url)
            card = self._card(tree, activity)
            self.assertEqual(self._icons(card), ['o_pk_card_trash', 'o_pk_card_edit'], url)
            self.assertTrue(card.xpath('.//template[@data-sc-lazy-edit]'), url)
            self.assertTrue(tree.xpath('//dialog[@id="sc_activity_detail_sheet"]'), url)
        # The dashboard's « Overdue activities » cards.
        self.act_player.date_deadline = fields.Date.today().replace(year=2020)
        _text, tree = self._get('/my/home')
        card = tree.xpath('//details[@data-sc-todo="activities_overdue"]'
                          '//*[@data-sc-activity-row="%s"]' % self.act_player.id)
        self.assertTrue(card)
        self.assertEqual(self._icons(card[0]), ['o_pk_card_trash', 'o_pk_card_edit'])
        self.assertTrue(tree.xpath('//dialog[@id="sc_activity_detail_sheet"]'))
        self.assertEqual(card[0].xpath('.//a[contains(@class, "o_pk_link_row_main")]/@data-sc-sheet-url'),
                         ['/my/activity/%s/popout' % self.act_player.id])

    def test_coach_assignee_field_follows_reassign_right(self):
        """A coach acts on their own activities (pencil); the assignee
        choices are the staff of their teams (the same rule as before)."""
        self._switch(True)
        self._login('coach')
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        card = self._card(tree, self.act_coach_assigned)
        self.assertEqual(self._icons(card), ['o_pk_card_trash', 'o_pk_card_edit'])
        props = {p['field']: p for p in self._props(card)}
        self.assertEqual(set(props), set(FIELDS))
        options = {str(o[0]) for o in props['user_id']['options']}
        self.assertIn(str(self.coach.id), options)
        self.assertNotIn(str(self.tp_b.id), options, 'a therapist of another team')

    # -- AC-3 --------------------------------------------------------------
    def test_no_pencil_without_act_right(self):
        from unittest.mock import patch
        from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import AccessControlMixin
        self._switch(True)
        self._login('tp')
        with patch.object(AccessControlMixin, '_activity_act_access', return_value=False):
            _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        card = self._card(tree, self.act_player)
        self.assertNotIn('o_pk_edit_card', card.get('class'))
        self.assertIsNone(card.get('data-pk-edit-card'))
        self.assertEqual(self._icons(card), [])
        self.assertFalse(card.xpath('.//*[@data-sc-edit-view] | .//owl-component | .//template'))
        self.assertFalse(card.xpath('.//*[@data-sc-action="activity.complete"]'))
        # The popout stays (who may open it is checked by its route).
        self.assertTrue(card.xpath('.//a[@data-sc-sheet-url]'))

    # -- AC-4 --------------------------------------------------------------
    def test_inline_saves(self):
        self._switch(True)
        self._login('tp')
        self.assertEqual(self._save(self.act_player, 'date_deadline', '2031-03-04').status_code, 200)
        self.assertEqual(self._save(self.act_player, 'user_id', str(self.coach.id)).status_code, 200)
        self.assertEqual(self._save(self.act_player, 'note', 'SC1736r1 new note').status_code, 200)
        self.act_player.invalidate_recordset()
        self.assertEqual(str(self.act_player.date_deadline), '2031-03-04')
        self.assertEqual(self.act_player.user_id, self.coach)
        self.assertIn('SC1736r1 new note', self.act_player.note)
        # An assignee outside my list: refused, nothing written.
        resp = self._save(self.act_player, 'user_id', str(self.plain.id))
        self.assertEqual(resp.status_code, 400)
        self.act_player.invalidate_recordset()
        self.assertEqual(self.act_player.user_id, self.coach)
        # Someone who may not act on it: refused.
        self._login('tp_b')
        with mute_logger('odoo.http'):
            self.assertIn(self._save(self.act_player, 'date_deadline', '2032-01-01').status_code, (403, 404))
        self.act_player.invalidate_recordset()
        self.assertEqual(str(self.act_player.date_deadline), '2031-03-04')

    # -- AC-5 --------------------------------------------------------------
    def test_unique_field_ids_across_tabs(self):
        self._switch(True)
        self._login('tp')
        _text, tree = self._get('/my/activities')
        cards = tree.xpath('//*[@data-sc-activity-row="%s"]' % self.act_team.id)
        self.assertEqual(len(cards), 2, '« All » and its state tab')
        ids = [p['inputId'] for card in cards for p in self._props(card)]
        self.assertEqual(len(ids), len(set(ids)), ids)
        keys = [card.get('data-pk-edit-card') for card in cards]
        self.assertEqual(len(set(keys)), 2, keys)

    # -- AC-6 / AC-7 -------------------------------------------------------
    def test_popout_link_and_body(self):
        self._switch(True)
        self._login('coach')
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        card = self._card(tree, self.act_coach_created)
        link = card.xpath('.//a[contains(@class, "o_pk_link_row_main")]')[0]
        self.assertEqual(link.get('href'), '/my/activity/%s' % self.act_coach_created.id)
        self.assertEqual(link.get('data-sc-sheet-open'), 'sc_activity_detail_sheet')
        self.assertEqual(link.get('data-sc-sheet-url'), '/my/activity/%s/popout' % self.act_coach_created.id)
        self.assertEqual(link.get('aria-haspopup'), 'dialog')
        sheet = tree.xpath('//dialog[@id="sc_activity_detail_sheet"]')
        self.assertEqual(len(sheet), 1)
        # The body.
        attachment = self.env['ir.attachment'].create({
            'name': 'sc1736r1-synthetic.txt', 'raw': b'synthetic',
            'res_model': 'mail.activity', 'res_id': self.act_coach_created.id})
        self.act_coach_created.write({'note': '<p>SC1736r1 coach note</p>'})
        resp = self.url_open('/my/activity/%s/popout' % self.act_coach_created.id)
        self.assertEqual(resp.status_code, 200)
        body = lxml_html.fromstring(resp.text)
        root = body.xpath('//*[@data-pk-section="activity.popout"]')
        self.assertTrue(root)
        text = ' '.join(root[0].text_content().split())
        for expected in ('Coach created task', 'Due Date', 'Assigned To', 'PC TP', 'Created',
                         'Created by', 'PC Coach', 'SC1736r1 coach note', 'sc1736r1-synthetic.txt'):
            self.assertIn(expected, text)
        self.assertTrue(root[0].xpath('.//*[@data-pk-section="activity.related"]//a[@href]'),
                        'the related record link')
        self.assertTrue(root[0].xpath('.//a[@href="/my/activity/%s/attachment/%s"]'
                                      % (self.act_coach_created.id, attachment.id)))
        self.assertTrue(root[0].xpath('.//*[contains(@class, "o_pk_chip")]'), 'the state chip')
        # Read-only: no control, no in-place refresh keys.
        self.assertFalse(root[0].xpath('.//owl-component | .//button | .//form | .//input'))
        self.assertFalse(root[0].xpath('.//*[@data-sc-fragment or @data-sc-display]'))

    def test_popout_refused(self):
        self._switch(True)
        self._login('coach')
        with mute_logger('odoo.http'):
            self.assertEqual(self.url_open('/my/activity/%s/popout' % self.act_player.id).status_code, 404)
            self._login('tp_b')
            self.assertEqual(self.url_open('/my/activity/%s/popout' % self.act_player.id).status_code, 404)
            self.assertEqual(self.url_open('/my/activity/999999/popout').status_code, 404)

    # -- AC-8 --------------------------------------------------------------
    def test_deep_link_page(self):
        self._switch(True)
        self._login('coach')
        _text, tree = self._get('/my/activity/%s' % self.act_coach_created.id)
        card = tree.xpath('//section[@data-pk-section="activity.detail"]')[0]
        text = ' '.join(card.text_content().split())
        self.assertIn('Created by', text)
        self.assertIn('PC Coach', text)
        self.assertTrue(card.xpath('.//*[@data-sc-fragment="mail.activity:%s:read"]' % self.act_coach_created.id))
        self.assertEqual(tree.xpath('//*[contains(@class, "o_pk_actionbar")]//@data-sc-action'),
                         ['activity.complete'])

    # -- AC-9 --------------------------------------------------------------
    def test_event_cancel_is_its_own_action(self):
        self._switch(True)
        self._login('tp')
        _text, tree = self._get('/my/event/%s' % self.event.id)
        hero = tree.xpath('//section[@data-pk-section="event.hero"]')[0]
        self.assertFalse(hero.xpath('.//*[@data-sc-card-icons]//*[@data-sc-action="event.cancel"]'))
        self.assertFalse(hero.xpath('.//*[contains(@class, "o_pk_card_archive")]'))
        cancel = hero.xpath('.//*[contains(@class, "o_pk_actions_row")]/button[@data-sc-action="event.cancel"]')
        self.assertEqual(len(cancel), 1)
        self.assertIn('o_pk_btn_danger', cancel[0].get('class'))
        self.assertEqual(cancel[0].get('data-sc-sheet-open'), 'sc_event_cancel_sheet')
        self.assertTrue(hero.xpath('.//*[@data-sc-card-icons]//a[contains(@class, "o_sc_card_clock")]'))


@tagged('post_install', '-at_install')
class TestActivityCards1736r1I18n(ActivityCards1736r1Common):
    """AC-10 — website-aware (the project CI installs website)."""

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

    def test_french(self):
        self._switch(True)
        self._login('coach')
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        _text, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        self.assertEqual(tree.xpath('//dialog[@id="sc_activity_detail_sheet"]//h2/text()'), ['Activité'])
        card = self._card(tree, self.act_coach_created)
        self.assertEqual(card.xpath('.//*[@data-sc-action="activity.complete"]//span/text()'), ['Terminé'])
        self.assertEqual(card.xpath('.//button[contains(@class, "o_pk_card_edit")]/@aria-label'), ['Modifier'])
        labels = [p['label'] for p in self._props(card)]
        self.assertEqual(labels, ['Résumé', "Date d'échéance", 'Assigné à', 'Note'])
        resp = self.url_open('/my/activity/%s/popout' % self.act_coach_created.id)
        text = ' '.join(lxml_html.fromstring(resp.text).text_content().split())
        self.assertIn('Créé par', text)
        self.assertIn('Créée le', text)
        self.assertIn("Date d'échéance", text)
