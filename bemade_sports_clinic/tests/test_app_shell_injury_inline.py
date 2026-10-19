"""Player page Injuries tab — add and edit injuries inline (owner decision
2026-10-11, mockup shown to MC). Synthetic fixtures only.

Acceptance criteria:

* UC-IJ1 « Add Injury » opens an inline card. A therapist first answers ONLY
  « Can coaches see this injury? » — Yes / No, nothing pre-selected, the
  answer required — and the diagnosis field with a « Create » button comes
  after. A coach (who cannot hide an injury) gets the diagnosis and
  « Create » directly. No device-draft banner.
* UC-IJ2 « Create » makes the injury from the diagnosis alone (today's date)
  with the chosen visibility, and lands back on the Injuries tab with that
  injury open in edit mode (``created=<id>``, ``#injury-<id>``), the team
  context kept.
* UC-IJ3 A therapist's create without a visibility answer creates nothing
  and comes back with an error. A coach's report lands « Unverified »,
  visible to coaches.
* UC-IJ4 The just-created injury offers a 2-minute « Undo »: the creator,
  within 2 minutes, with no treatment note or document on it, deletes it;
  anyone else, later, or once it carries a note or document, is refused
  and the injury stays.
* UC-IJ5 Every injury in the list expands inline: a read view of its
  details (date, predicted return, visibility, consent, notes — therapist
  fields for therapists only) with ONE pencil revealing its autosave fields,
  and a link to the injury page (treatment notes, documents, history).
* UC-IJ6 A therapist sees « Consent to complete » on an injury without
  parental consent; a coach never does.
* UC-IJ7 The card and the injury cards render in French (fr_CA).
* UC-IJ8 (owner 2026-10-11) Setting the status to « Resolved » answers the
  resolution date it set (value + display), so the open card's date field and
  read view show it at once, without a reload (browser half: the
  ``sc_injury_resolve_date`` tour).
"""
from datetime import timedelta
from urllib.parse import urlparse

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_player_inline import PlayerInlineCommon


@tagged('post_install', '-at_install')
class TestAppShellInjuryInline(PlayerInlineCommon):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _tab(self, **extra):
        return self._url(tab='injuries', team_id=self.team_a.id, **extra)

    def _add_card(self, tree):
        panel = tree.xpath('//section[@data-sc-tab-panel="injuries"]')[0]
        cards = panel.xpath('.//details[@id="sc_new_injury"][@data-sc-section="injury.new"]')
        self.assertEqual(len(cards), 1)
        return cards[0]

    def _create(self, **data):
        payload = {
            'csrf_token': self._csrf(), 'patient_id': self.player.id, 'sc_inline': '1',
            'team_context_id': self.team_a.id,
        }
        payload.update(data)
        return self.url_open('/my/patient/injury/create', data=payload, allow_redirects=False)

    def _new_injury(self, diagnosis):
        return self.env['sports.patient.injury'].search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', diagnosis)])

    # -- UC-IJ1 ----------------------------------------------------------
    def test_add_card_steps(self):
        self._login_tp()
        _text, tree = self._get(self._tab())
        card = self._add_card(tree)
        form = card.xpath('.//form[@data-sc-form="injury.quick"]')[0]
        self.assertEqual(form.get('action'), '/my/patient/injury/create')
        radios = form.xpath('.//input[@type="radio"][@name="coach_visibility"]')
        self.assertEqual(sorted(r.get('value') for r in radios), ['hidden', 'visible'])
        self.assertFalse([r for r in radios if r.get('checked') is not None])
        self.assertTrue(all(r.get('required') is not None for r in radios))
        step = form.xpath('.//*[@data-sc-step="diagnosis"]')[0]
        self.assertTrue(step.xpath('.//input[@name="diagnosis"][@required]'))
        self.assertTrue(step.xpath('.//button[@type="submit"][@data-sc-action="injury.create"]'))
        self.assertFalse(card.xpath('.//*[contains(@class, "o_sc_banner")]'))
        self.assertFalse(card.xpath('.//owl-component'))
        self._login_coach()
        _text, tree = self._get(self._tab())
        form = self._add_card(tree).xpath('.//form[@data-sc-form="injury.quick"]')[0]
        self.assertFalse(form.xpath('.//input[@name="coach_visibility"]'))
        self.assertTrue(form.xpath('.//input[@name="diagnosis"][@required]'))

    # -- UC-IJ2 ----------------------------------------------------------
    def test_create_lands_on_open_injury(self):
        self._login_tp()
        resp = self._create(diagnosis='Synthetic ankle', coach_visibility='hidden')
        self.assertEqual(resp.status_code, 303, resp.text[:300])
        injury = self._new_injury('Synthetic ankle')
        self.assertEqual(len(injury), 1)
        self.assertTrue(injury.hidden_from_coaches)
        self.assertEqual(injury.injury_date, fields.Date.context_today(injury))
        self.assertEqual(injury.stage, 'active')
        location = resp.headers['Location']
        self.assertIn('tab=injuries', location)
        self.assertIn('team_id=%s' % self.team_a.id, location)
        self.assertIn('created=%s' % injury.id, location)
        self.assertTrue(location.endswith('#injury-%s' % injury.id))
        parts = urlparse(location)
        _text, tree = self._get('%s?%s' % (parts.path, parts.query))
        item = tree.xpath('//details[@id="injury-%s"]' % injury.id)[0]
        self.assertIsNotNone(item.get('open'))
        self.assertEqual(item.get('data-sc-created-injury'), str(injury.id))
        edit = item.xpath('.//*[@data-sc-edit-view="edit"]')[0]
        self.assertIsNone(edit.get('hidden'))
        self.assertTrue(item.xpath('.//form[@data-sc-form="injury.undo"]'))
        self._create(diagnosis='Synthetic wrist', coach_visibility='visible')
        self.assertFalse(self._new_injury('Synthetic wrist').hidden_from_coaches)

    # -- UC-IJ3 ----------------------------------------------------------
    def test_visibility_required_and_coach_report(self):
        self._login_tp()
        resp = self._create(diagnosis='Synthetic knee')
        self.assertEqual(resp.status_code, 303)
        self.assertFalse(self._new_injury('Synthetic knee'))
        self.assertIn('error=', resp.headers['Location'])
        self._login_coach()
        self._create(diagnosis='Synthetic shin', coach_visibility='hidden')
        report = self._new_injury('Synthetic shin')
        self.assertEqual(report.stage, 'unverified')
        self.assertFalse(report.hidden_from_coaches)

    # -- UC-IJ4 ----------------------------------------------------------
    def _undo(self, injury):
        return self.url_open('/my/injury/%s/undo-create' % injury.id, data={
            'csrf_token': self._csrf(), 'team_id': self.team_a.id,
        }, allow_redirects=False)

    @mute_logger('odoo.addons.bemade_sports_clinic.controllers.patient_injury_portal')
    def test_undo_rules(self):
        self._login_tp()
        self._create(diagnosis='Synthetic undo', coach_visibility='visible')
        injury = self._new_injury('Synthetic undo')
        # Someone else: refused.
        self._login_coach()
        self._undo(injury)
        self.assertTrue(injury.exists())
        # Too late: refused.
        self._login_tp()
        self.env.cr.execute("UPDATE sports_patient_injury SET create_date=%s WHERE id=%s",
                            (fields.Datetime.now() - timedelta(minutes=3), injury.id))
        injury.invalidate_recordset()
        self._undo(injury)
        self.assertTrue(injury.exists())
        # In time, by the creator: deleted, back on the Injuries tab.
        self.env.cr.execute("UPDATE sports_patient_injury SET create_date=%s WHERE id=%s",
                            (fields.Datetime.now(), injury.id))
        injury.invalidate_recordset()
        resp = self._undo(injury)
        self.assertFalse(injury.exists())
        self.assertIn('tab=injuries', resp.headers['Location'])
        # A treatment note on it: refused.
        self._create(diagnosis='Synthetic noted', coach_visibility='visible')
        noted = self._new_injury('Synthetic noted')
        self.env['sports.treatment.note'].sudo().create({
            'patient_id': self.player.id, 'injury_id': noted.id, 'note': 'Synthetic note',
        })
        self._undo(noted)
        self.assertTrue(noted.exists())

    # -- UC-IJ5 / UC-IJ6 -------------------------------------------------
    def test_injury_items_expand_with_pencil(self):
        self.injury.sudo().write({'external_notes': 'Synthetic ext', 'internal_notes': 'Synthetic int',
                                  'parental_consent': False})
        self._login_tp()
        _text, tree = self._get(self._tab())
        item = tree.xpath('//details[@id="injury-%s"][@data-sc-edit-card]' % self.injury.id)[0]
        self.assertIsNone(item.get('open'))
        # Task 1616: the read views (Details, then Notes), one pencil per
        # group; together they edit what the card's single pencil did.
        reads = ' '.join(r.text_content() for r in item.xpath('.//*[@data-sc-edit-view="read"]'))
        self.assertIn('Synthetic ext', reads)
        self.assertIn('Synthetic int', reads)
        self.assertEqual(len(item.xpath('.//button[@data-sc-edit-toggle]')), 2)
        edits = item.xpath('.//*[@data-sc-edit-view="edit"]')
        self.assertTrue(all(edit.get('hidden') == 'hidden' for edit in edits))
        fields_ = ' '.join(f for edit in edits for f in self._fields_in(edit))
        for name in ('"sc_injury_date"', '"predicted_resolution_date"', '"parental_consent"',
                     '"external_notes"', '"internal_notes"', '"hidden_from_coaches"', '"stage"'):
            self.assertIn(name, fields_)
        self.assertFalse(item.xpath('.//a[contains(@href, "/my/injury/edit")]'))
        self.assertTrue(item.xpath('.//summary//*[contains(@class, "o_sc_consent_todo")]'))
        self._login_coach()
        _text, tree = self._get(self._tab())
        item = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        self.assertNotIn('Synthetic int', item.text_content())
        self.assertFalse(item.xpath('.//*[contains(@class, "o_sc_consent_todo")]'))
        fields_ = ' '.join(self._fields_in(item))
        self.assertIn('"external_notes"', fields_)
        self.assertNotIn('"internal_notes"', fields_)
        self.assertNotIn('"parental_consent"', fields_)

    # -- UC-IJ8 ----------------------------------------------------------
    def test_resolve_answers_resolution_date(self):
        self.injury.sudo().write({'resolution_date': False})
        self._login_tp()
        resp = self._save(self.injury, 'stage', 'resolved')
        self.assertEqual(resp.status_code, 200, resp.text)
        also = resp.json().get('also') or {}
        today = fields.Date.context_today(self.injury)
        self.assertEqual(also.get('resolution_date', {}).get('value'), fields.Date.to_string(today))
        self.assertTrue(also['resolution_date'].get('display'))

@tagged('post_install', '-at_install')
class TestAppShellInjuryInlineTour(PlayerInlineCommon):
    """UC-IJ1 / UC-IJ2 / UC-IJ4 in the browser: the visibility question
    first, the diagnosis after it, « Create », the edit view and « Undo »."""

    def test_inline_create_and_undo(self):
        self._switch(True)
        self.start_tour(self._url(tab='injuries', team_id=self.team_a.id),
                        'sc_injury_inline_create', login='pc.tp@example.com')
        self.assertFalse(self.env['sports.patient.injury'].search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', 'Synthetic tour ankle')]))


@tagged('post_install', '-at_install')
class TestAppShellInjuryInlineFr(TestAppShellI18n1538):
    """UC-IJ7."""

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None

    def test_injuries_tab_in_french(self):
        self.injury.sudo().write({'parental_consent': False})
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/player?player_id=%s&tab=injuries' % self.player.id).replace('&#39;', "'")
        for term in ('Les entraîneurs peuvent-ils voir cette blessure ?', 'Non, la masquer',
                     'Consentement à compléter', 'Détails', 'Ajouter des documents',
                     'Date de la blessure'):
            self.assertIn(term, text, term)


@tagged('post_install', '-at_install')
class TestAppShellInjuryResolveTour(PlayerInlineCommon):
    """UC-IJ8 in the browser."""

    def test_resolve_refreshes_date(self):
        self._switch(True)
        self.injury.sudo().write({'resolution_date': False})
        self.start_tour(self._url(tab='injuries', team_id=self.team_a.id, injury=self.injury.id),
                        'sc_injury_resolve_date', login='pc.tp@example.com')
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertTrue(self.injury.resolution_date)
