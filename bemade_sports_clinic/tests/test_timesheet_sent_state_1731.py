"""Task 1731 — make « submitted » obvious on a timesheet (UX only: no state,
invoicing or missing-timesheet change). Synthetic fixtures only (this
repository is public).

There is no separate « send » step: creating a timesheet IS sending it
(state ``submitted``). A therapist could not tell, so:

Acceptance criteria:

* UC-1 Every timesheet card (event page, « Feuilles de temps » list) shows its
  state chip: « Submitted ✓ » (« Soumise ✓ », green) for a submitted one,
  « Billed » (« Facturée ») for an invoiced one.
* UC-2 Adding a timesheet lands back on the event with « Timesheet sent. »
  (« Feuille de temps envoyée. »); the new timesheet is ``submitted`` (no
  workflow change).
* UC-3 An own editable card's edit view carries the one-line hint « Your
  timesheet for this event has already been sent — your changes are saved
  automatically. » and its four autosave fields read « Sent · hh:mm »
  (``savedLabel``) once saved; another therapist's read-only card has
  neither.
* UC-4 The « Sent » wording is scoped to timesheet cards: other autosave
  fields (the event card) keep the generic « Saved ».
* UC-5 fr_CA (website-aware): « Soumise ✓ », « Facturée », « Feuille de
  temps envoyée. », the French hint and « Envoyée ».
* UC-6 In a browser (phone width): « Add My Timesheet » with an existing
  timesheet opens its card in edit with the hint visible; an edit saves and
  reads « Sent · hh:mm »
  (static/tests/tours/sc_timesheet_sent_1731_tours.js).
"""
import json

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

HINT_EN = ('Your timesheet for this event has already been sent — your changes '
           'are saved automatically.')
HINT_FR = ('Votre feuille de temps pour cet événement est déjà envoyée — vos '
           "modifications s'enregistrent automatiquement.")
TS_FIELDS = ('travel_start', 'coverage_start', 'coverage_end', 'travel_end')


class TimesheetSent1731Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'SC1731 Other Therapist', 'login': 'sc1731.tp2@example.com',
            'password': 'sc1731-tp2-pass',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist',
        })
        # A second, already-invoiced timesheet of the therapist's (another event).
        cls.event_billed = env['sports.event'].create({
            'name': 'SC1731 Billed Event', 'event_type': 'game',
            'team_ids': [Command.set([cls.team_a.id])],
            'date_start': cls.event.date_start, 'date_end': cls.event.date_end,
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([cls.tp.id])],
        })
        cls.ts_billed = env['sports.event.timesheet'].create({
            'event_id': cls.event_billed.id, 'user_id': cls.tp.id,
        })
        cls.ts_billed.sudo().write({'state': 'invoiced'})

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _tree(self, url):
        _text, tree = self._get(url)
        return tree

    @staticmethod
    def _card(tree, ts):
        cards = tree.xpath('//article[@data-sc-timesheet-id="%s"]' % ts.id)
        return cards[0] if cards else None

    @staticmethod
    def _chip(card):
        chips = card.xpath('.//*[@data-sc-ts-state]')
        return chips[0] if chips else None

    @staticmethod
    def _text(node):
        return ' '.join(node.text_content().split())

    @staticmethod
    def _props(card):
        return [json.loads(p) for p in card.xpath('.//owl-component/@props')]

    @staticmethod
    def _hint(card):
        hints = card.xpath('.//*[@data-sc-ts-sent-hint]')
        return ' '.join(hints[0].text_content().split()) if hints else None


@tagged('post_install', '-at_install')
class TestTimesheetSent1731(TimesheetSent1731Common):

    # -- UC-1 -------------------------------------------------------------
    def test_event_page_chip_submitted(self):
        self._login_tp()
        card = self._card(self._tree('/my/event/%s' % self.event.id), self.timesheet)
        chip = self._chip(card)
        self.assertEqual(chip.get('data-sc-ts-state'), 'submitted')
        self.assertEqual(self._text(chip), 'Submitted ✓')
        self.assertIn('o_sc_chip_green', chip.get('class'))

    def test_timesheets_list_chips(self):
        self._login_tp()
        tree = self._tree('/my/sc/timesheets')
        submitted = self._chip(self._card(tree, self.timesheet))
        billed = self._chip(self._card(tree, self.ts_billed))
        self.assertEqual(self._text(submitted), 'Submitted ✓')
        self.assertEqual(billed.get('data-sc-ts-state'), 'invoiced')
        self.assertEqual(self._text(billed), 'Billed')
        self.assertNotIn('o_sc_chip_green', billed.get('class'))

    # -- UC-2 -------------------------------------------------------------
    def test_add_says_sent(self):
        Timesheet = self.env['sports.event.timesheet']
        before = Timesheet.search([('event_id', '=', self.event.id)])
        self._login_tp()
        resp = self.url_open('/my/event/%s/timesheet/add' % self.event.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        self.assertIn('ts_saved=1', resp.headers['Location'])
        new = Timesheet.search([('event_id', '=', self.event.id)]) - before
        self.assertEqual(len(new), 1)
        self.assertEqual(new.state, 'submitted', 'no workflow change: created = submitted')
        text, _tree = self._get(resp.headers['Location'])
        self.assertIn('Timesheet sent.', text)
        self.assertNotIn('Timesheet saved.', text)

    # -- UC-3 -------------------------------------------------------------
    def test_editable_card_hint_and_sent_label(self):
        self._login_tp()
        card = self._card(self._tree('/my/event/%s' % self.event.id), self.timesheet)
        self.assertEqual(card.get('data-sc-edit-card'), 'timesheet-%s' % self.timesheet.id)
        hint = card.xpath('.//*[@data-sc-edit-view="edit"]//*[@data-sc-ts-sent-hint]')
        self.assertTrue(hint, 'the hint sits in the edit view')
        self.assertEqual(self._hint(card), HINT_EN)
        props = {p['field']: p for p in self._props(card)}
        self.assertEqual(set(props), set(TS_FIELDS))
        for field in TS_FIELDS:
            self.assertEqual(props[field].get('savedLabel'), 'Sent', field)

    def test_read_only_cards_have_no_hint(self):
        # The invoiced card (read-only) and another therapist's card.
        self._login_tp()
        billed = self._card(self._tree('/my/sc/timesheets'), self.ts_billed)
        self.assertIsNone(self._hint(billed))
        self.assertFalse(self._props(billed))
        ts_other = self.env['sports.event.timesheet'].create({
            'event_id': self.event.id, 'user_id': self.tp2.id,
        })
        self.event.write({'assigned_staff_ids': [Command.link(self.tp2.id)]})
        self.authenticate('sc1731.tp2@example.com', 'sc1731-tp2-pass')
        tree = self._tree('/my/event/%s' % self.event.id)
        own = self._card(tree, ts_other)
        self.assertEqual(self._hint(own), HINT_EN)
        self.assertIsNone(self._card(tree, self.timesheet), 'a therapist sees only her own')

    # -- UC-4 -------------------------------------------------------------
    def test_sent_label_scoped_to_timesheets(self):
        self._login_tp()
        tree = self._tree('/my/event/%s' % self.event.id)
        others = [json.loads(p) for p in tree.xpath(
            '//owl-component[not(ancestor::article[@data-sc-timesheet-id])]/@props')]
        self.assertTrue(others, 'the event page has other autosave fields')
        self.assertFalse([p for p in others if p.get('savedLabel')])


@tagged('post_install', '-at_install')
class TestTimesheetSentFr1731(TimesheetSent1731Common):
    """UC-5 — fr_CA (website-aware: fr_CA on the website + frontend_lang)."""

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
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        return self._get(url)

    def test_french(self):
        self._login_tp()
        _text, tree = self._fr('/my/sc/timesheets')
        self.assertEqual(self._text(self._chip(self._card(tree, self.timesheet))), 'Soumise ✓')
        self.assertEqual(self._text(self._chip(self._card(tree, self.ts_billed))), 'Facturée')
        _text, tree = self._fr('/my/event/%s' % self.event.id)
        card = self._card(tree, self.timesheet)
        self.assertEqual(self._hint(card), HINT_FR)
        self.assertEqual({p.get('savedLabel') for p in self._props(card)}, {'Envoyée'})
        resp = self.url_open('/my/event/%s/timesheet/add' % self.event.id,
                             data={'csrf_token': self._csrf()}, allow_redirects=False)
        text, _tree = self._fr(resp.headers['Location'])
        self.assertIn('Feuille de temps envoyée.', text)


@tagged('post_install', '-at_install')
class TestTimesheetSentTour1731(TimesheetSent1731Common):
    """UC-6 in a browser, phone width."""
    browser_size = '390x844'

    def test_existing_timesheet_sent_hint_and_label(self):
        self.start_tour('/my/event/%s' % self.event.id, 'sc_1731_timesheet_sent',
                        login='pc.tp@example.com')
