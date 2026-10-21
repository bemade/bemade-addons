"""Task 1631 — the injury card: the header status pill is a dropdown (the
#1627 component), going backward proposes to undo the dates, consent and
visibility are pill dropdowns side by side, ONE notes « Historique ».
Synthetic fixtures only (this repository is public).

Use case: a therapist corrects an injury's status from the card header —
forward exactly as today (« Résolu » asks the resolution date, then the
#1603 popup), backward (a mistake) with a popup proposing to undo the dates
that followed the previous status; consent and visibility are changed in
two taps; the notes have one history, both scopes labelled.

Acceptance criteria:

* AC-1 Header pill (therapist): the card's ``<summary>`` holds the stage as
  a ``sc_status_pill_select`` dropdown (``data-sc-pill-key="stage"``,
  tones Non vérifié yellow / Actif red / Résolu green) next to the
  unchanged quick « Vérifier » / « Résoudre » button; no ``stage`` autosave
  field anywhere in the card. Picking « Actif » from « Non vérifié » is the
  verify action (``data-sc-pill-action="injury.verify"``), picking
  « Résolu » from an unresolved status the resolve sheet
  (``injury.resolve``); every other (backward) pick posts ``stage``.
* AC-2 Coach: the same coloured stage chip, read-only (no button, no menu),
  and no consent / visibility pill.
* AC-3 Forward moves behave as today: the resolve route takes an
  unverified injury only when the pill says so (``from_unverified=1``),
  closing its verification To-Do; without it, still 400.
* AC-4 Backward moves answer ONE proposal (``kind`` « moved_back ») — never
  the forward builders' — and log « Injury moved back to <status> by
  <user> »:
  - Résolu -> Actif: clear the resolution date; restore the predicted
    resolution date wiped by the resolve (from tracking; an empty editable
    date when there is none); clear the player's actual return when it is
    this resolution date; Retour prévu = the latest predicted date of the
    active injuries, this one included;
  - Actif -> Non vérifié: Retour prévu recomputed from the remaining active
    injuries (cleared when none is left);
  - Résolu -> Non vérifié: the resolution date + actual return + the
    Retour prévu recompute.
  Applying it (``/my/app/apply-proposal``, ``resolution_date`` now allowed
  on the injury) writes the dates.
* AC-5 Consent + visibility: two pill dropdowns in one row
  (``o_sc_injury_flags``) inside Details, inside a read fragment
  (``flags``) — consent Oui green / Non red / S/O neutral / blank yellow
  « To be specified » (pickable), visibility Coaches neutral / Hidden
  yellow; saves post the existing fields; the Details edit view no longer
  holds stage / consent / visibility.
* AC-6 Notes: ONE « History » (the Notes head, all scopes), no per-field
  History and no per-scope sheets.
* AC-7 French: « Consentement parental : Oui », « À préciser »,
  « Visibilité : Entraîneurs », the backward popup and chatter line.
* AC-8 (browser, tour ``sc_1631_injury_card``): Actif -> Résolu from the
  pill (date sheet + popup), Résolu -> Actif (backward popup, apply, dates
  in place), consent and visibility pill changes, one Historique, Effacer
  then a new note -> one history entry.
"""
import json
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient_injury import VERIFY_INJURY_SUMMARY
from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon

D = fields.Date.to_date


class InjuryCard1631Mixin:

    def _url(self):
        return '/my/player?player_id=%s&tab=injuries' % self.player.id

    def _card(self, tree, injury=None, prefix='injury-'):
        injury = injury or self.injury
        nodes = tree.xpath('//details[@id="%s%s"]' % (prefix, injury.id))
        self.assertEqual(len(nodes), 1, 'one card for injury %s' % injury.id)
        return nodes[0]

    @staticmethod
    def _pill(scope, key):
        nodes = scope.xpath('.//*[@data-sc-pill-key="%s"]' % key)
        return nodes[0] if nodes else None

    @staticmethod
    def _items(tree, pill):
        toggle = pill.xpath('.//button[contains(@class, "o_sc_pill_select")]')[0]
        popup = tree.xpath('//*[@id="%s"]' % toggle.get('aria-controls'))[0]
        return {item.get('data-sc-pill-value'): item
                for item in popup.xpath('.//*[@role="menuitemradio"]')}

    @staticmethod
    def _fields(scope):
        return [json.loads(node.get('props')).get('field')
                for node in scope.xpath('.//owl-component[@name="bemade_sports_clinic.sc_autosave_field"]')]

    def _apply(self, changes, patient=None):
        return self.url_open('/my/app/apply-proposal', data={
            'patient_id': (patient or self.player).id,
            'changes': json.dumps(changes),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _resolve(self, injury, day, **extra):
        return self.url_open('/my/injury/%s/resolve' % injury.id, data=dict({
            'csrf_token': self._csrf(), 'resolution_date': day}, **extra), allow_redirects=False)

    @staticmethod
    def _by_key(proposal):
        return {(item['model'], item['id'], item['field']): item for item in proposal['items']}


@tagged('post_install', '-at_install')
class TestInjuryCard1631(InjuryCard1631Mixin, FragmentsCommon):

    def setUp(self):
        super().setUp()
        self.player.sudo().write({'predicted_return_date': False, 'return_date': False})

    # -- AC-1 ------------------------------------------------------------
    def test_header_pill_is_a_dropdown(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        card = self._card(tree)
        summary = card.xpath('./summary')[0]
        pill = self._pill(summary, 'stage')
        self.assertIsNotNone(pill, 'the stage pill sits in the summary')
        self.assertEqual(pill.get('data-sc-model'), 'sports.patient.injury')
        self.assertEqual(pill.get('data-sc-record-id'), str(self.injury.id))
        self.assertEqual(pill.get('data-sc-field'), 'stage')
        self.assertEqual(pill.get('data-sc-old-value'), 'active')
        toggle = pill.xpath('.//button[contains(@class, "o_sc_pill_select")]')[0]
        self.assertEqual(toggle.get('aria-haspopup'), 'menu')
        self.assertIn('o_sc_chip_red', toggle.get('class'))
        items = self._items(tree, pill)
        self.assertEqual(list(items), ['unverified', 'active', 'resolved'])
        tones = {value: item.xpath('.//span[contains(@class, "o_sc_pill_swatch")]')[0].get('class')
                 for value, item in items.items()}
        self.assertIn('o_sc_chip_yellow', tones['unverified'])
        self.assertIn('o_sc_chip_red', tones['active'])
        self.assertIn('o_sc_chip_green', tones['resolved'])
        self.assertEqual(items['active'].get('aria-checked'), 'true')
        self.assertEqual(items['resolved'].get('data-sc-pill-action'), 'injury.resolve')
        self.assertIsNone(items['unverified'].get('data-sc-pill-action'))
        self.assertEqual(items['unverified'].get('data-sc-pill-post'), 'unverified')
        # The quick « Résoudre » stays, one tap.
        self.assertTrue(summary.xpath('.//button[@data-sc-injury-quick="resolve"]'))
        # No in-body status selector any more.
        self.assertNotIn('stage', self._fields(card))
        # The static status chip is gone from the row.
        self.assertFalse(summary.xpath('.//span[contains(@class, "o_sc_row_trailing")]'
                                       '/span[contains(concat(" ", @class, " "), " o_sc_chip ")]'))

    def test_unverified_pill_actions(self):
        self.injury.sudo().with_context(mail_notrack=True).write({'stage': 'unverified'})
        self._login_tp()
        _text, tree = self._get(self._url())
        pill = self._pill(self._card(tree).xpath('./summary')[0], 'stage')
        items = self._items(tree, pill)
        self.assertEqual(items['active'].get('data-sc-pill-action'), 'injury.verify')
        self.assertEqual(items['resolved'].get('data-sc-pill-action'), 'injury.resolve')
        self.assertEqual(items['resolved'].get('data-sc-pill-from'), 'unverified')

    def test_resolved_pill_moves_back_only(self):
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': D('2026-03-01')})
        self._login_tp()
        _text, tree = self._get(self._url())
        pill = self._pill(self._card(tree).xpath('./summary')[0], 'stage')
        self.assertIn('o_sc_chip_green', pill.xpath('.//button')[0].get('class'))
        items = self._items(tree, pill)
        for value in ('unverified', 'active'):
            self.assertIsNone(items[value].get('data-sc-pill-action'), value)
            self.assertEqual(items[value].get('data-sc-pill-post'), value)

    # -- AC-2 ------------------------------------------------------------
    def test_coach_sees_read_only_chips(self):
        self._login_coach()
        _text, tree = self._get(self._url())
        card = self._card(tree)
        pill = self._pill(card.xpath('./summary')[0], 'stage')
        self.assertIsNotNone(pill)
        self.assertEqual(pill.get('data-sc-pill-readonly'), '1')
        self.assertIn('o_sc_chip_red', pill.get('class'))
        self.assertFalse(card.xpath('.//button[contains(@class, "o_sc_pill_select")]'))
        self.assertIsNone(self._pill(card, 'consent'))
        self.assertIsNone(self._pill(card, 'visibility'))

    # -- AC-3 ------------------------------------------------------------
    def test_resolve_from_unverified_via_the_pill(self):
        self.injury.sudo().with_context(mail_notrack=True).write({'stage': 'unverified'})
        todo = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'res_id': self.player.id, 'injury_id': self.injury.id,
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'summary': '[Injury: Sprain] %s' % VERIFY_INJURY_SUMMARY, 'user_id': self.tp.id,
        })
        self._login_tp()
        resp = self._resolve(self.injury, '2026-03-02')
        self.assertEqual(resp.status_code, 400, 'the plain button path still refuses')
        resp = self._resolve(self.injury, '2026-03-02', from_unverified='1')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'resolved')
        self.assertEqual(self.injury.resolution_date, D('2026-03-02'))
        self.assertFalse(todo.exists() and todo.active)

    def test_forward_save_keeps_the_forward_proposal(self):
        """Unverified -> active through a save (the pill's « Annuler »)
        still proposes Retour prévu as before (one source)."""
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'stage': 'unverified', 'predicted_resolution_date': D('2026-05-01')})
        self._login_tp()
        payload = self._saved(self.injury, 'stage', 'active')
        self.assertEqual(payload['propose']['kind'], 'retour_prevu')

    # -- AC-4 ------------------------------------------------------------
    def test_resolved_to_active_restores_the_dates(self):
        # A FUTURE predicted date (a past one is replaced by « a week ahead »).
        future = fields.Date.context_today(self.injury) + timedelta(days=30)
        future_s = fields.Date.to_string(future)
        self.injury.write({'predicted_resolution_date': future})
        self.env.cr.flush()
        self._login_tp()
        resp = self._resolve(self.injury, '2026-03-10')
        self.assertEqual(resp.status_code, 200, resp.text)
        # The proposal of the resolve was applied: actual return set.
        self.player.sudo().write({'return_date': D('2026-03-10')})
        self.injury.invalidate_recordset()
        self.assertFalse(self.injury.predicted_resolution_date)
        payload = self._saved(self.injury, 'stage', 'active', old_value='resolved')
        proposal = payload['propose']
        self.assertEqual(proposal['kind'], 'moved_back')
        self.assertEqual(proposal['patient_id'], self.player.id)
        items = self._by_key(proposal)
        inj, pat = 'sports.patient.injury', 'sports.patient'
        self.assertEqual(set(items), {
            (inj, self.injury.id, 'resolution_date'),
            (inj, self.injury.id, 'predicted_resolution_date'),
            (pat, self.player.id, 'return_date'),
            (pat, self.player.id, 'predicted_return_date'),
        })
        res = items[(inj, self.injury.id, 'resolution_date')]
        self.assertEqual((res['current'], res['proposed']), ('2026-03-10', ''))
        pred = items[(inj, self.injury.id, 'predicted_resolution_date')]
        self.assertEqual(pred['proposed'], future_s, 'restored from tracking')
        self.assertTrue(pred['editable'])
        ret = items[(pat, self.player.id, 'return_date')]
        self.assertEqual((ret['current'], ret['proposed']), ('2026-03-10', ''))
        prevu = items[(pat, self.player.id, 'predicted_return_date')]
        self.assertEqual(prevu['proposed'], future_s)
        # The chatter line.
        self.assertTrue(self.injury.message_ids.filtered(
            lambda m: 'moved back to' in (m.body or '') and 'Active' in (m.body or '')))
        # Apply everything.
        resp = self._apply([{'model': i['model'], 'id': i['id'], 'field': i['field'],
                             'value': i['proposed']} for i in proposal['items']])
        self.assertEqual(resp.status_code, 200, resp.text)
        self.injury.invalidate_recordset()
        self.player.invalidate_recordset()
        self.assertFalse(self.injury.resolution_date)
        self.assertEqual(self.injury.predicted_resolution_date, D(future_s))
        self.assertFalse(self.player.return_date)
        self.assertEqual(self.player.predicted_return_date, D(future_s))

    def test_resolved_to_active_without_tracking_proposes_a_week_ahead(self):
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': D('2026-03-10')})
        self._login_tp()
        proposal = self._saved(self.injury, 'stage', 'active')['propose']
        items = self._by_key(proposal)
        pred = items[('sports.patient.injury', self.injury.id, 'predicted_resolution_date')]
        # Owner review 2026-10-20: never an empty or past date — a week ahead.
        week = fields.Date.context_today(self.injury) + timedelta(days=7)
        self.assertEqual(pred['proposed'], fields.Date.to_string(week))
        self.assertTrue(pred['editable'])
        # The player's actual return differs: left alone.
        self.assertNotIn(('sports.patient', self.player.id, 'return_date'), items)

    def test_active_to_unverified_recomputes_retour_prevu(self):
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic knee 1631'})
        other.with_context(mail_notrack=True).write(
            {'stage': 'active', 'predicted_resolution_date': D('2026-04-01')})
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'predicted_resolution_date': D('2026-05-01')})
        self.player.sudo().write({'predicted_return_date': D('2026-05-01')})
        self._login_tp()
        proposal = self._saved(self.injury, 'stage', 'unverified')['propose']
        self.assertEqual(proposal['kind'], 'moved_back')
        self.assertEqual(len(proposal['items']), 1, proposal['items'])
        item = proposal['items'][0]
        self.assertEqual((item['model'], item['field']), ('sports.patient', 'predicted_return_date'))
        self.assertEqual((item['current'], item['proposed']), ('2026-05-01', '2026-04-01'))

    def test_active_to_unverified_last_one_clears_retour_prevu(self):
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'predicted_resolution_date': D('2026-05-01')})
        self.player.sudo().write({'predicted_return_date': D('2026-05-01')})
        self._login_tp()
        proposal = self._saved(self.injury, 'stage', 'unverified')['propose']
        item = self._by_key(proposal)[('sports.patient', self.player.id, 'predicted_return_date')]
        self.assertEqual(item['proposed'], '')

    def test_resolved_to_unverified(self):
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': D('2026-03-10')})
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic knee 1631'})
        other.with_context(mail_notrack=True).write(
            {'stage': 'active', 'predicted_resolution_date': D('2026-04-01')})
        self.player.sudo().write({'return_date': D('2026-03-10')})
        self._login_tp()
        proposal = self._saved(self.injury, 'stage', 'unverified')['propose']
        items = self._by_key(proposal)
        self.assertEqual(set(items), {
            ('sports.patient.injury', self.injury.id, 'resolution_date'),
            ('sports.patient', self.player.id, 'return_date'),
            ('sports.patient', self.player.id, 'predicted_return_date'),
        })
        self.assertEqual(items[('sports.patient', self.player.id, 'predicted_return_date')]['proposed'],
                         '2026-04-01')

    def test_moving_back_never_fires_a_forward_builder(self):
        """Résolu -> Actif with a matching Retour prévu: nothing to propose
        for it, and no « retour_prevu » proposal either."""
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': D('2026-03-10')})
        self._login_tp()
        payload = self._saved(self.injury, 'stage', 'active')
        self.assertEqual(payload['propose']['kind'], 'moved_back')

    def test_coach_never_moves_back(self):
        self._login_coach()
        resp = self._save(self.injury, 'stage', 'unverified')
        self.assertEqual(resp.status_code, 403)

    # -- AC-5 ------------------------------------------------------------
    def test_consent_and_visibility_pills(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        card = self._card(tree)
        details = card.xpath('.//section[@data-sc-edit-card="injury-details"]')[0]
        row = details.xpath('.//*[contains(@class, "o_sc_injury_flags")]')
        self.assertEqual(len(row), 1)
        row = row[0]
        self.assertEqual(row.get('data-sc-fragment'), 'sports.patient.injury:%s:flags' % self.injury.id)
        self.assertEqual([p.get('data-sc-pill-key') for p in row.xpath('.//*[@data-sc-pill-key]')],
                         ['consent', 'visibility'])
        consent = self._pill(row, 'consent')
        self.assertEqual(consent.get('data-sc-field'), 'parental_consent')
        self.assertEqual(consent.get('data-sc-old-value'), '')
        toggle = consent.xpath('.//button')[0]
        self.assertIn('o_sc_chip_yellow', toggle.get('class'))
        self.assertIn('To be specified', ' '.join(toggle.itertext()))
        items = self._items(tree, consent)
        self.assertEqual(list(items), ['yes', 'no', 'na', ''])
        swatch = {k: v.xpath('.//span[contains(@class, "o_sc_pill_swatch")]')[0].get('class')
                  for k, v in items.items()}
        self.assertIn('o_sc_chip_green', swatch['yes'])
        self.assertIn('o_sc_chip_red', swatch['no'])
        self.assertIn('o_sc_chip_ghost', swatch['na'])
        self.assertIn('o_sc_chip_yellow', swatch[''])
        self.assertEqual(items[''].get('data-sc-pill-post'), '', 'blank is pickable')
        visibility = self._pill(row, 'visibility')
        self.assertEqual(visibility.get('data-sc-field'), 'hidden_from_coaches')
        self.assertEqual(visibility.get('data-sc-old-value'), '0')
        self.assertIn('o_sc_chip_ghost', visibility.xpath('.//button')[0].get('class'))
        vitems = self._items(tree, visibility)
        self.assertEqual(list(vitems), ['0', '1'])
        self.assertIn('o_sc_chip_yellow',
                      vitems['1'].xpath('.//span[contains(@class, "o_sc_pill_swatch")]')[0].get('class'))
        # The Details edit view holds the dates only now.
        self.assertEqual(self._fields(details.xpath('.//*[@data-sc-edit-view="edit"]')[0]), [
            'diagnosis', 'sc_injury_date', 'predicted_resolution_date', 'resolution_date'])

    def test_pill_saves_refresh_the_flags(self):
        self._login_tp()
        key = 'sports.patient.injury:%s:flags' % self.injury.id
        payload = self._saved(self.injury, 'parental_consent', 'no', old_value='')
        self.assertRefreshes(payload, key)
        payload = self._saved(self.injury, 'hidden_from_coaches', '1', old_value='0')
        self.assertRefreshes(payload, key)
        node = self._fragment(self._url(), key)
        consent = self._pill(node, 'consent')
        self.assertIn('o_sc_chip_red', consent.xpath('.//button')[0].get('class'))
        self.assertEqual(consent.get('data-sc-old-value'), 'no')
        visibility = self._pill(node, 'visibility')
        self.assertIn('o_sc_chip_yellow', visibility.xpath('.//button')[0].get('class'))
        self.assertEqual(visibility.get('data-sc-old-value'), '1')
        self.assertFragmentMatchesPage(self._url(), key)
        # Back to blank.
        self._saved(self.injury, 'parental_consent', '', old_value='no')
        self.injury.invalidate_recordset()
        self.assertFalse(self.injury.parental_consent)

    # -- AC-6 ------------------------------------------------------------
    def test_single_notes_history(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        notes = self._card(tree).xpath('.//section[@data-sc-edit-card="injury-notes"]')[0]
        opens = notes.xpath('.//*[starts-with(@data-sc-sheet-open, "sc_note_history_sheet_")]')
        self.assertEqual(len(opens), 1)
        self.assertEqual(opens[0].get('data-sc-sheet-open'), 'sc_note_history_sheet_%s' % self.injury.id)
        self.assertTrue(opens[0].xpath('ancestor::div[contains(@class, "o_sc_edit_card_head")]'))
        for props in notes.xpath('.//owl-component/@props'):
            self.assertNotIn('historySheet', json.loads(props))
        self.assertEqual(notes.xpath('.//dialog[starts-with(@id, "sc_note_history_sheet_")]/@id'),
                         ['sc_note_history_sheet_%s' % self.injury.id])

    def test_history_labels_the_scopes(self):
        self.injury.sudo().write({'internal_notes': 'Synthetic internal 1631',
                                  'external_notes': 'Synthetic external 1631'})
        self._login_tp()
        text = self.url_open('/my/injury/%s/notes/history/fragment' % self.injury.id).text
        self.assertIn('Internal', text)
        self.assertIn('External', text)


@tagged('post_install', '-at_install')
class TestInjuryCardFrench1631(InjuryCard1631Mixin, FragmentsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        fr = env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr.id)]
        (cls.tp | cls.coach).write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text.replace('&#39;', "'")

    def test_french_pills(self):
        self._login_tp()
        text = self._fr(self._url())
        for term in ('Consentement parental : À préciser', 'Visibilité : Entraîneurs',
                     'Statut de la blessure'):
            self.assertIn(term, text)
        self.injury.sudo().write({'parental_consent': 'na', 'hidden_from_coaches': True})
        text = self._fr(self._url())
        self.assertIn('Consentement parental : S/O', text)
        self.assertIn('Visibilité : Masquée', text)

    def test_french_backward_popup_and_chatter(self):
        self.injury.sudo().with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': D('2026-03-10')})
        self._login_tp()
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        proposal = self._saved(self.injury, 'stage', 'active')['propose']
        self.assertEqual(proposal['title'], 'Corriger les dates ?')
        labels = {item['field']: item['label'] for item in proposal['items']}
        self.assertEqual(labels['resolution_date'], 'Date de résolution')
        self.assertEqual(labels['predicted_resolution_date'], 'Date prévue de résolution')
        bodies = ' '.join(self.injury.sudo().message_ids.mapped(lambda m: str(m.body or '')))
        self.assertIn('Blessure ramenée à Actif par', bodies)


@tagged('post_install', '-at_install')
class TestInjuryCardTours1631(InjuryCard1631Mixin, FragmentsCommon):

    def test_tour(self):
        self.player.sudo().write({'predicted_return_date': False, 'return_date': False})
        self.injury.sudo().write({'predicted_resolution_date': fields.Date.today() + timedelta(days=20),
                                  'external_notes': 'Synthetic external 1631'})
        self.env.cr.flush()
        before = self.env['sports.injury.note.history'].search_count(
            [('injury_id', '=', self.injury.id), ('scope', '=', 'external')])
        self.start_tour('%s&injury=%s#injury-%s' % (self._url(), self.injury.id, self.injury.id),
                        'sc_1631_injury_card', login='pc.tp@example.com')
        self.injury.invalidate_recordset()
        self.player.invalidate_recordset()
        self.assertEqual(self.injury.stage, 'active')
        self.assertFalse(self.injury.resolution_date)
        self.assertEqual(self.injury.predicted_resolution_date,
                         fields.Date.today() + timedelta(days=20))
        self.assertEqual(self.injury.parental_consent, 'yes')
        self.assertTrue(self.injury.hidden_from_coaches)
        self.assertEqual(self.injury.external_notes, 'Synthetic rewritten 1631')
        rows = self.env['sports.injury.note.history'].search(
            [('injury_id', '=', self.injury.id), ('scope', '=', 'external')], order='id asc')
        self.assertEqual(len(rows), before + 1, 'the clear was overwritten by the new note')
        self.assertEqual(rows[-1].content, 'Synthetic rewritten 1631')
