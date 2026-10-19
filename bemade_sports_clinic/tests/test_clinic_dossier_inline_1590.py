"""Task 1590 — the clinic dossier's injuries in the new look: the player
page's inline « Add Injury » card and pencil-edit cards (field-by-field
saving), with the two quick notes saved in place under their « last note »
stamp. Synthetic fixtures only (this repository is public).

Acceptance criteria:

* UC-CD1 The dossier (app shell) shows the inline add card and one pencil
  card per current injury — no legacy injury sheet / fragment URL. The add
  card posts ``sc_inline=1``, the clinic and ``sc_origin=clinic``; a card's
  notes are the replace-mode autosave fields carrying the « last note »
  stamp (``hint``), internal notes for therapists only.
* UC-CD2 An inline create from the dossier lands back on THAT clinic, same
  patient, file tab, with ``created=<id>`` and the card in view
  (``#clinic-injury-<id>``); the card renders open, in edit mode, with its
  « Undo » form posting the clinic origin again.
* UC-CD3 « Undo » from the dossier deletes the injury and returns to the
  dossier (``success=injury_undone``, flash shown); a refused undo also
  returns there with its error.
* UC-CD4 The player-page origin is unchanged: an inline create carrying a
  clinic as navigation context but NO ``sc_origin`` still lands on the
  player's Injuries tab (``#injury-<id>``), and so does its undo.
* UC-CD5 A just-created unverified injury (e.g. a coach's report) shows in
  the dossier — the dossier lists active AND unverified injuries, never
  resolved ones.
* UC-CD6 A quick note saved from a dossier card replaces the text, answers
  the refreshed stamp, and the dossier shows it under the field on reload.
* UC-CD7 Coach-hidden rules unchanged: a « hide it » create from the
  dossier is hidden from coaches (absent from the coach's player page); the
  dossier still shows it to the therapist with « Hidden from coaches »; a
  coach is still refused the clinic page.
* UC-CD8 The player page still renders through the shared card templates
  (ids ``sc_new_injury`` / ``injury-<id>``, no ``sc_origin``, no stamp).
"""
import json
from urllib.parse import urlparse, parse_qs

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_clinic_1540 import Clinic1540Common
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538


class ClinicDossier1590Common(Clinic1540Common):

    def setUp(self):
        super().setUp()
        self._switch(True)

    def _dossier_url(self, **extra):
        query = '&'.join('%s=%s' % kv for kv in extra.items())
        return '/my/clinic/%s?patient=%s&tab=dossier%s' % (
            self.clinic.id, self.player.id, ('&' + query) if query else '')

    def _create(self, origin='clinic', **data):
        payload = {
            'csrf_token': self._csrf(), 'patient_id': self.player.id, 'sc_inline': '1',
            'clinic_id': self.clinic.id, 'team_context_id': self.team_a.id,
        }
        if origin:
            payload['sc_origin'] = origin
        payload.update(data)
        return self.url_open('/my/patient/injury/create', data=payload, allow_redirects=False)

    def _undo(self, injury, origin='clinic'):
        payload = {'csrf_token': self._csrf(), 'clinic_id': self.clinic.id, 'team_id': self.team_a.id}
        if origin:
            payload['sc_origin'] = origin
        return self.url_open('/my/injury/%s/undo-create' % injury.id, data=payload,
                             allow_redirects=False)

    def _new_injury(self, diagnosis):
        return self.env['sports.patient.injury'].search(
            [('patient_id', '=', self.player.id), ('diagnosis', '=', diagnosis)])

    @staticmethod
    def _props(scope):
        out = {}
        for node in scope.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]'):
            props = json.loads(node.get('props'))
            out[props.get('field') or props.get('name')] = props
        return out

    def _follow(self, location):
        parts = urlparse(location)
        return self._get('%s?%s' % (parts.path, parts.query))


@tagged('post_install', '-at_install')
class TestClinicDossierInline1590(ClinicDossier1590Common):

    # -- UC-CD1 ----------------------------------------------------------
    def test_dossier_has_inline_cards(self):
        self.injury.sudo().write({'external_notes': 'Synthetic ext 1590'})
        self._login_tp()
        text, tree = self._get(self._dossier_url())
        section = tree.xpath('//section[@data-sc-section="clinic.dossier.injuries"]')[0]
        add = section.xpath('.//details[@id="sc_clinic_injury_add"][@data-sc-section="injury.new"]')
        self.assertEqual(len(add), 1)
        form = add[0].xpath('.//form[@data-sc-form="injury.quick"]')[0]
        self.assertEqual(form.get('action'), '/my/patient/injury/create')
        hidden = {i.get('name'): i.get('value') for i in form.xpath('.//input[@type="hidden"]')}
        self.assertEqual(hidden['sc_inline'], '1')
        self.assertEqual(hidden['patient_id'], str(self.player.id))
        self.assertEqual(hidden['clinic_id'], str(self.clinic.id))
        self.assertEqual(hidden['sc_origin'], 'clinic')
        self.assertTrue(form.xpath('.//input[@name="coach_visibility"][@required]'))
        cards = section.xpath('.//details[@data-sc-edit-card="injury"]')
        self.assertEqual([c.get('id') for c in cards], ['clinic-injury-%s' % self.injury.id])
        card = cards[0]
        # Task 1611: no reload on « Done » — the card is a read-fragment
        # list item (its summary and read view refresh in place).
        self.assertIsNone(card.get('data-sc-edit-reload'))
        self.assertEqual(card.get('data-sc-fragment-item'), 'sports.patient.injury:%s:card' % self.injury.id)
        self.assertTrue(card.xpath('.//button[@data-sc-edit-toggle]'))
        props = self._props(card)
        for fname in ('external_notes', 'internal_notes'):
            self.assertIs(props[fname].get('replace'), True)
        self.assertIn('stage', props)
        self.injury.invalidate_recordset()
        self.assertEqual(props['external_notes'].get('hint'), self.injury.last_external_note_info)
        self.assertTrue(props['external_notes'].get('hint'))
        # No legacy sheet / fragment on the shell dossier any more.
        self.assertFalse(tree.xpath('//dialog[starts-with(@id, "sc_clinic_injury_")]'))
        self.assertNotIn('/form/fragment', text)
        self.assertNotIn('/my/patient/injury/new/fragment', text)
        # « New injury » in the hero jumps to the inline card.
        self.assertEqual(tree.xpath('//a[@data-sc-action="clinic.injury_new"]/@href'),
                         ['#sc_clinic_injury_add'])

    # -- UC-CD2 ----------------------------------------------------------
    def test_create_lands_back_on_dossier(self):
        self._login_tp()
        resp = self._create(diagnosis='Synthetic 1590 ankle', coach_visibility='visible')
        self.assertEqual(resp.status_code, 303, resp.text[:300])
        injury = self._new_injury('Synthetic 1590 ankle')
        self.assertEqual(len(injury), 1)
        self.assertEqual(injury.stage, 'active')
        location = resp.headers['Location']
        parts = urlparse(location)
        self.assertEqual(parts.path, '/my/clinic/%s' % self.clinic.id)
        query = parse_qs(parts.query)
        self.assertEqual(query['patient'], [str(self.player.id)])
        self.assertEqual(query['tab'], ['dossier'])
        self.assertEqual(query['created'], [str(injury.id)])
        self.assertEqual(parts.fragment, 'clinic-injury-%s' % injury.id)
        _text, tree = self._follow(location)
        dossier = tree.xpath('//section[@data-sc-tab-panel="dossier"]')[0]
        self.assertIsNone(dossier.get('hidden'))
        card = tree.xpath('//details[@id="clinic-injury-%s"]' % injury.id)[0]
        self.assertIsNotNone(card.get('open'))
        self.assertEqual(card.get('data-sc-created-injury'), str(injury.id))
        self.assertIsNone(card.xpath('.//*[@data-sc-edit-view="edit"]')[0].get('hidden'))
        undo = card.xpath('.//form[@data-sc-form="injury.undo"]')[0]
        self.assertEqual(undo.get('action'), '/my/injury/%s/undo-create' % injury.id)
        self.assertEqual(undo.xpath('.//input[@name="sc_origin"]/@value'), ['clinic'])
        self.assertEqual(undo.xpath('.//input[@name="clinic_id"]/@value'), [str(self.clinic.id)])
        # ?injury= (what the page turns ?created= into) opens it read-only.
        _text, tree = self._get(self._dossier_url(injury=injury.id))
        card = tree.xpath('//details[@id="clinic-injury-%s"]' % injury.id)[0]
        self.assertIsNotNone(card.get('open'))
        self.assertIsNone(card.get('data-sc-created-injury'))
        self.assertFalse(card.xpath('.//form[@data-sc-form="injury.undo"]'))

    def test_create_errors_land_on_dossier(self):
        self._login_tp()
        resp = self._create(diagnosis='Synthetic 1590 knee')
        self.assertFalse(self._new_injury('Synthetic 1590 knee'))
        location = resp.headers['Location']
        self.assertTrue(location.startswith(
            '/my/clinic/%s?patient=%s&tab=dossier' % (self.clinic.id, self.player.id)), location)
        self.assertIn('error=injury_visibility', location)
        text, _tree = self._follow(location)
        self.assertIn('Please choose whether coaches can see this injury.', text)

    # -- UC-CD3 ----------------------------------------------------------
    def test_undo_returns_to_dossier(self):
        self._login_tp()
        self._create(diagnosis='Synthetic 1590 undo', coach_visibility='visible')
        injury = self._new_injury('Synthetic 1590 undo')
        resp = self._undo(injury)
        self.assertFalse(injury.exists())
        location = resp.headers['Location']
        self.assertEqual(
            location, '/my/clinic/%s?patient=%s&tab=dossier&success=injury_undone#clinic-injuries' % (
                self.clinic.id, self.player.id))
        text, _tree = self._follow(location)
        self.assertIn('Injury creation undone.', text)

    @mute_logger('odoo.addons.bemade_sports_clinic.controllers.patient_injury_portal')
    def test_refused_undo_returns_to_dossier(self):
        self._login_tp()
        self._create(diagnosis='Synthetic 1590 noted', coach_visibility='visible')
        injury = self._new_injury('Synthetic 1590 noted')
        self.env['sports.treatment.note'].sudo().create({
            'patient_id': self.player.id, 'injury_id': injury.id, 'note': 'Synthetic note 1590',
        })
        resp = self._undo(injury)
        self.assertTrue(injury.exists())
        location = resp.headers['Location']
        self.assertTrue(location.startswith('/my/clinic/%s?' % self.clinic.id), location)
        self.assertIn('error=undo_expired', location)
        text, _tree = self._follow(location)
        self.assertIn('This injury can no longer be undone; delete it from its card.', text)

    # -- UC-CD4 ----------------------------------------------------------
    def test_player_page_origin_unchanged(self):
        self._login_tp()
        resp = self._create(origin=None, diagnosis='Synthetic 1590 player', coach_visibility='visible')
        injury = self._new_injury('Synthetic 1590 player')
        location = resp.headers['Location']
        parts = urlparse(location)
        self.assertEqual(parts.path, '/my/player')
        query = parse_qs(parts.query)
        self.assertEqual(query['tab'], ['injuries'])
        self.assertEqual(query['clinic_id'], [str(self.clinic.id)])
        self.assertEqual(query['created'], [str(injury.id)])
        self.assertEqual(parts.fragment, 'injury-%s' % injury.id)
        resp = self._undo(injury, origin=None)
        self.assertFalse(injury.exists())
        parts = urlparse(resp.headers['Location'])
        self.assertEqual(parts.path, '/my/player')
        self.assertIn('success=injury_undone', parts.query)
        # A forged origin without a (valid) clinic is ignored too.
        resp = self._create(diagnosis='Synthetic 1590 forged', coach_visibility='visible',
                            clinic_id='999999')
        self.assertEqual(urlparse(resp.headers['Location']).path, '/my/player')

    # -- UC-CD5 ----------------------------------------------------------
    def test_unverified_injury_shows_resolved_does_not(self):
        Injury = self.env['sports.patient.injury']
        unverified = Injury.create({'patient_id': self.player.id, 'diagnosis': 'Synthetic 1590 report'})
        unverified.with_context(mail_notrack=True).write({'stage': 'unverified'})
        resolved = Injury.create({'patient_id': self.player.id, 'diagnosis': 'Synthetic 1590 old'})
        resolved.with_context(mail_notrack=True).write({'stage': 'resolved'})
        self._login_tp()
        _text, tree = self._get(self._dossier_url())
        ids = tree.xpath('//section[@data-sc-section="clinic.dossier.injuries"]'
                         '//details[@data-sc-edit-card="injury"]/@data-sc-injury-id')
        self.assertIn(str(unverified.id), ids)
        self.assertIn(str(self.injury.id), ids)
        self.assertNotIn(str(resolved.id), ids)
        # A coach's report from the player page (unverified) shows in the
        # therapist's dossier as soon as it exists.
        self._login_coach()
        self._create(origin=None, clinic_id='', diagnosis='Synthetic 1590 coach report')
        report = self._new_injury('Synthetic 1590 coach report')
        self.assertEqual(report.stage, 'unverified')
        self._login_tp()
        _text, tree = self._get(self._dossier_url())
        card = tree.xpath('//details[@id="clinic-injury-%s"]' % report.id)
        self.assertTrue(card)
        self.assertIn('o_sc_tone_yellow', ' '.join(card[0].xpath('.//summary//span/@class')))

    # -- UC-CD6 ----------------------------------------------------------
    def test_quick_note_saves_with_stamp(self):
        self._login_tp()
        self.injury.invalidate_recordset()
        resp = self.url_open('/my/app/save/sports.patient.injury/%s' % self.injury.id, data={
            'field': 'external_notes', 'value': 'Synthetic 1590 current state',
            'write_date': fields.Datetime.to_string(self.injury.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        answer = resp.json()
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.external_notes, 'Synthetic 1590 current state')
        self.assertTrue(self.injury.last_external_note_info)
        self.assertEqual(answer.get('hint'), self.injury.last_external_note_info)
        _text, tree = self._get(self._dossier_url())
        card = tree.xpath('//details[@id="clinic-injury-%s"]' % self.injury.id)[0]
        props = self._props(card)
        self.assertEqual(props['external_notes']['value'], 'Synthetic 1590 current state')
        self.assertEqual(props['external_notes']['hint'], self.injury.last_external_note_info)

    # -- UC-CD7 ----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_coach_hidden_rules_unchanged(self):
        self._login_tp()
        self._create(diagnosis='Synthetic 1590 hidden', coach_visibility='hidden')
        hidden = self._new_injury('Synthetic 1590 hidden')
        self.assertTrue(hidden.hidden_from_coaches)
        _text, tree = self._get(self._dossier_url())
        card = tree.xpath('//details[@id="clinic-injury-%s"]' % hidden.id)[0]
        self.assertTrue(card.xpath('.//*[contains(@class, "o_sc_chip_mauve")]'))
        self._login_coach()
        text, tree = self._get('/my/player?player_id=%s&tab=injuries' % self.player.id)
        self.assertFalse(tree.xpath('//details[@id="injury-%s"]' % hidden.id))
        self.assertNotIn('Synthetic 1590 hidden', text)
        resp = self.url_open(self._dossier_url())
        self.assertNotEqual(resp.status_code, 200)

    # -- UC-CD8 ----------------------------------------------------------
    def test_player_page_cards_unchanged(self):
        self._login_tp()
        _text, tree = self._get('/my/player?player_id=%s&team_id=%s&tab=injuries' % (
            self.player.id, self.team_a.id))
        add = tree.xpath('//details[@id="sc_new_injury"]')
        self.assertEqual(len(add), 1)
        self.assertFalse(add[0].xpath('.//input[@name="sc_origin"]'))
        card = tree.xpath('//details[@id="injury-%s"]' % self.injury.id)[0]
        props = self._props(card)
        self.assertNotIn('hint', props['external_notes'])
        self.assertIs(props['external_notes'].get('replace'), True)


@tagged('post_install', '-at_install')
class TestClinicDossierInlineFr1590(TestAppShellI18n1538):
    """The dossier's inline cards and the undo flash in French (fr_CA)."""

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_dossier_cards_in_french(self):
        clinic = self.env['sports.event'].create({
            'name': 'SC 1590 FR Clinic', 'event_type': 'clinic',
            'team_ids': [Command.set([self.team_a.id])],
            'date_start': fields.Datetime.now(),
            'date_end': fields.Datetime.add(fields.Datetime.now(), hours=2),
            'state': 'confirmed',
            'assigned_staff_ids': [Command.set([self.tp.id])],
        })
        self.env['sports.clinic.attendance'].create(
            {'event_id': clinic.id, 'patient_id': self.player.id})
        self.injury.sudo().write({'parental_consent': False, 'hidden_from_coaches': True})
        self._switch(True)
        self._login_tp()
        text = self._fr('/my/clinic/%s?patient=%s&tab=dossier&success=injury_undone' % (
            clinic.id, self.player.id)).replace('&#39;', "'")
        for term in ('Ajouter une blessure', 'Les entraîneurs peuvent-ils voir cette blessure ?',
                     'Non, la masquer', 'Consentement à compléter',
                     'Détails', 'Ajouter des documents',
                     'Masquée aux entraîneurs', 'Création de la blessure annulée.'):
            self.assertIn(term, text, term)
