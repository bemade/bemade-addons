"""Owner review fixes from the /dev-review UAT of 2026-10-18 (server half;
the browser half is tests/test_review_fixes_tours_1018.py). Synthetic
fixtures only.

Acceptance criteria covered here:

* RF-1606 « Paramètres » has no « Portail classique » row (Langue, Mon
  compte, Sécurité stay).
* RF-1617 The events LIST filter panel is collapsed on every visit, even
  with a filter active (the calendar keeps its own rule).
* RF-CREATE The app-shell create forms submit with « Créer » (EN
  « Create »): the event create form, the player create form, the
  therapist's new-injury form.
* RF-DATES (a) An injury card shows « Date prévue de résolution » until the
  injury is resolved and « Date de résolution » once it is (read view; the
  edit view's holders are hidden the same way). (b) Resolving an injury —
  app stage save, quick « Résoudre », ``action_resolve_injury``, a plain
  write, a create already resolved — clears ``predicted_resolution_date``
  (the stage save answers it under ``also``). (c) The 19.0.1.86.0 cleanup
  nulls it on already-resolved injuries only, without chatter; an
  unresolved injury carrying a resolution date is untouched.
* RF-HEADER (see test_header_order_1615) the player header's read view +
  pencil; here: « Remove player » only in its edit view.
"""
from datetime import date

from lxml import html as lxml_html

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


def _text(node):
    return ' '.join(node.text_content().split())


@tagged('post_install', '-at_install')
class TestReviewFixes1018(PlayerInlineCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    # -- RF-1606 ---------------------------------------------------------
    def test_settings_without_classic_portal(self):
        self._login_tp()
        _text_, tree = self._get('/my/app/settings')
        main = tree.xpath('//main[@id="sc_content"]')[0]
        hrefs = set(main.xpath('.//a/@href'))
        self.assertIn('/my/account', hrefs)
        self.assertIn('/my/security', hrefs)
        self.assertFalse([h for h in hrefs if 'classic=1' in h])
        self.assertTrue(main.xpath('.//section[@id="sc_account"]'))

    # -- RF-1617 ---------------------------------------------------------
    def test_events_list_filters_closed_even_when_filtered(self):
        self._login_tp()
        for url in ('/my/events',
                    '/my/events?team_id=%s&show_cancelled=1&group_by=team' % self.team_a.id):
            _text_, tree = self._get(url)
            form = tree.xpath('//form[@data-sc-section="events.filters"]')[0]
            details = form.xpath('.//details[contains(@class, "o_sc_disclosure")]')
            self.assertEqual(len(details), 1)
            self.assertIsNone(details[0].get('open'), url)
            # The filter is still applied and shown in the (closed) panel.
            if 'team_id' in url:
                self.assertEqual(form.xpath('.//select[@name="team_id"]/option[@selected]/@value'),
                                 [str(self.team_a.id)])
        # The calendar keeps opening its panel on an active filter.
        _text_, tree = self._get('/my/events/calendar?team_id=%s' % self.team_a.id)
        self.assertTrue(tree.xpath('//form[@data-sc-section="events.filters"]//details[@open]'))

    # -- RF-CREATE -------------------------------------------------------
    def _submit_label(self, url, selector):
        _text_, tree = self._get(url)
        buttons = tree.xpath(selector)
        self.assertEqual(len(buttons), 1, url)
        return _text(buttons[0])

    def test_create_buttons_read_create(self):
        self._login_tp()
        self.assertEqual(self._submit_label('/my/event/create', '//button[@data-sc-action="event.save"]'),
                         'Create')
        self.assertEqual(self._submit_label('/my/player/create?first_name=Zed&last_name=Synthetic',
                                            '//button[@data-sc-action="player.create.submit"]'), 'Create')
        self.assertEqual(self._submit_label('/my/patient/injury/new?patient_id=%s' % self.player.id,
                                            '//form//button[@data-sc-action="injury.create"]'), 'Create')

    # -- RF-DATES (a) ----------------------------------------------------
    def _card(self, injury):
        _text_, tree = self._get(self._url(tab='injuries', injury=injury.id))
        cards = tree.xpath('//details[@id and .//*[@data-sc-fragment="sports.patient.injury:%s:read"]]' % injury.id)
        self.assertEqual(len(cards), 1)
        return cards[0]

    def test_card_shows_the_date_for_the_status(self):
        injury = self.injury.sudo()
        injury.write({'predicted_resolution_date': '2030-03-01'})
        self._login_tp()
        card = self._card(injury)
        read = _text(card.xpath('.//*[@data-sc-fragment="sports.patient.injury:%s:read"]' % injury.id)[0])
        self.assertIn('Predicted Resolution Date', read)
        self.assertNotIn('Resolution Date', read.replace('Predicted Resolution Date', ''))
        predicted = card.xpath('.//*[@data-sc-stage-of="%s"][@data-sc-stage-hide="resolved"]' % injury.id)[0]
        resolved = card.xpath('.//*[@data-sc-stage-of="%s"][@data-sc-stage-show="resolved"]' % injury.id)[0]
        self.assertIsNone(predicted.get('hidden'))
        self.assertEqual(resolved.get('hidden'), 'hidden')
        self.assertIn('"predicted_resolution_date"', ' '.join(predicted.xpath('.//owl-component/@props')))
        self.assertIn('"resolution_date"', ' '.join(resolved.xpath('.//owl-component/@props')))
        # Resolved: the resolution date, not the predicted one.
        injury.action_resolve_injury(resolution_date=date(2026, 10, 1))
        card = self._card(injury)
        read = _text(card.xpath('.//*[@data-sc-fragment="sports.patient.injury:%s:read"]' % injury.id)[0])
        self.assertNotIn('Predicted Resolution Date', read)
        self.assertIn('Resolution Date', read)
        predicted = card.xpath('.//*[@data-sc-stage-of="%s"][@data-sc-stage-hide="resolved"]' % injury.id)[0]
        resolved = card.xpath('.//*[@data-sc-stage-of="%s"][@data-sc-stage-show="resolved"]' % injury.id)[0]
        self.assertEqual(predicted.get('hidden'), 'hidden')
        self.assertIsNone(resolved.get('hidden'))

    # -- RF-DATES (b) ----------------------------------------------------
    def _new_injury(self, **vals):
        return self.env['sports.patient.injury'].create(dict({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic strain',
            'stage': 'active', 'predicted_resolution_date': '2030-03-01',
        }, **vals))

    def test_resolving_clears_the_predicted_date_every_path(self):
        # Model action.
        injury = self._new_injury()
        injury.action_resolve_injury()
        self.assertFalse(injury.predicted_resolution_date)
        self.assertTrue(injury.resolution_date)
        # Plain write (backend form save), even when the predicted date is
        # posted along.
        injury = self._new_injury()
        injury.write({'stage': 'resolved', 'predicted_resolution_date': '2030-04-01'})
        self.assertFalse(injury.predicted_resolution_date)
        # Created already resolved.
        injury = self._new_injury(stage='resolved')
        self.assertFalse(injury.predicted_resolution_date)
        # Other writes keep it.
        injury = self._new_injury()
        injury.write({'stage': 'active', 'diagnosis': 'Synthetic strain 2'})
        self.assertEqual(injury.predicted_resolution_date, date(2030, 3, 1))

    def test_app_stage_save_and_quick_resolve_clear_it(self):
        self._login_tp()
        injury = self._new_injury()
        resp = self._save(injury, 'stage', 'resolved')
        self.assertEqual(resp.status_code, 200, resp.text)
        injury.invalidate_recordset()
        self.assertFalse(injury.predicted_resolution_date)
        also = resp.json().get('also') or {}
        self.assertIn('predicted_resolution_date', also)
        self.assertFalse(also['predicted_resolution_date']['value'])
        injury = self._new_injury()
        resp = self.url_open('/my/injury/%s/resolve' % injury.id, data={
            'csrf_token': self._csrf(), 'resolution_date': fields.Date.to_string(fields.Date.today()),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text)
        injury.invalidate_recordset()
        self.assertEqual(injury.stage, 'resolved')
        self.assertFalse(injury.predicted_resolution_date)
        self.assertIn('predicted_resolution_date', resp.json()['also'])

    # -- RF-DATES (c) ----------------------------------------------------
    def test_cleanup_nulls_resolved_only_without_chatter(self):
        Injury = self.env['sports.patient.injury']
        resolved = self._new_injury()
        resolved.action_resolve_injury()
        unresolved = self._new_injury(resolution_date='2026-09-01')
        # Legacy data: a resolved injury still carrying a predicted date.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE sports_patient_injury SET predicted_resolution_date = '2030-05-05' WHERE id = %s",
            (resolved.id,))
        resolved.invalidate_recordset()
        self.assertTrue(resolved.predicted_resolution_date)
        messages = self.env['mail.message'].search_count([
            ('model', '=', 'sports.patient.injury'), ('res_id', 'in', (resolved | unresolved).ids)])
        self.assertGreaterEqual(Injury._sc_clear_resolved_predicted_dates(), 1)
        resolved.invalidate_recordset()
        unresolved.invalidate_recordset()
        self.assertFalse(resolved.predicted_resolution_date)
        self.assertEqual(unresolved.predicted_resolution_date, date(2030, 3, 1))
        self.assertEqual(unresolved.resolution_date, date(2026, 9, 1))
        self.assertEqual(unresolved.stage, 'active')
        self.assertEqual(self.env['mail.message'].search_count([
            ('model', '=', 'sports.patient.injury'), ('res_id', 'in', (resolved | unresolved).ids)]),
            messages)
        # Idempotent.
        self.assertEqual(Injury._sc_clear_resolved_predicted_dates(), 0)

    # -- RF-HEADER -------------------------------------------------------
    def test_remove_player_only_in_the_header_edit_view(self):
        self._login_tp()
        _text_, tree = self._get(self._url(tab='injuries', team_id=self.team_a.id))
        hero = tree.xpath('//*[@data-sc-section="player.hero"]')[0]
        removes = hero.xpath('.//*[@data-sc-action="player.remove"]')
        for node in removes:
            self.assertTrue(node.xpath('ancestor::*[@data-sc-edit-view="edit"]'))
        self.assertFalse(hero.xpath('./*[@data-sc-edit-view="read"]//*[@data-sc-action="player.remove"]'))
        self.assertFalse(hero.xpath('./*[contains(@class, "o_sc_actions_row")]//*[@data-sc-action="player.remove"]'))


@tagged('post_install', '-at_install')
class TestReviewFixes1018I18n(TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _button(self, url, selector):
        tree = lxml_html.fromstring(self._fr(url))
        return [_text(b) for b in tree.xpath(selector)]

    def test_create_buttons_in_french(self):
        self._login_tp()
        self.assertEqual(self._button('/my/event/create', '//button[@data-sc-action="event.save"]'), ['Créer'])
        self.assertEqual(self._button('/my/player/create?first_name=Zed&last_name=Synthetic', '//button[@data-sc-action="player.create.submit"]'),
                         ['Créer'])
        self.assertEqual(self._button('/my/patient/injury/new?patient_id=%s' % self.player.id,
                                      '//form//button[@data-sc-action="injury.create"]'), ['Créer'])

    def test_header_labels_in_french(self):
        self.player.sudo().write({'match_status': 'yes', 'practice_status': 'yes', 'return_date': '2026-11-02'})
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/player?player_id=%s' % self.player.id))
        ret = tree.xpath('//*[@data-sc-section="player.return"]')[0]
        self.assertIn('Retour réel', _text(ret))
        toggle = tree.xpath('//*[@data-sc-section="player.hero"]/button[@data-sc-edit-toggle]')[0]
        self.assertEqual(toggle.get('aria-label'), 'Modifier')
