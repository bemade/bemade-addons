"""Task 1603 — the player's « Retour prévu » (predicted return date) in the
player page header, kept coherent with the injuries' predicted resolution
dates through FOLLOW-UP PROPOSALS. Synthetic fixtures only.

Owner decisions (2026-10-17): therapists only; « mismatch » = any
difference from the latest predicted resolution date among the player's
ACTIVE injuries; resolving the last active injury proposes clearing Retour
prévu AND setting the actual return date to the resolution date; no
backfill; a proposal never blocks the save that triggered it.

Acceptance criteria:

* AC-1 Header field: a therapist edits « Retour prévu » in the player
  header (server autosave of ``predicted_return_date``, clearable); a coach
  reads it (static, a read fragment) and a coach's save is refused (403);
  an invalid date is refused (400).
* AC-2 Injury -> player: saving an ACTIVE injury's predicted resolution date
  answers 200 with ``propose`` (kind ``retour_prevu``): one editable item,
  the player's ``predicted_return_date``, proposed = the LATEST predicted
  resolution date among the player's active injuries (resolved / unverified
  injuries ignored). No proposal when it already equals Retour prévu, when
  no active injury has a date, or for a non-active injury.
* AC-3 Player -> injuries: saving Retour prévu answers ``propose`` (kind
  ``align_injuries``) when it differs from the latest active predicted
  resolution date — earlier OR later: one ticked, tickable item per active
  injury whose date differs, proposed = the new player date. No proposal
  when equal, when cleared, or when the player has no active injury.
* AC-4 Resolve: resolving the player's LAST active injury answers
  ``propose`` (kind ``last_resolved``): clear Retour prévu (when set) and set
  the actual return date (editable) = the injury's resolution date.
  Resolving another active injury proposes nothing.
* AC-5 Apply: POST /my/app/apply-proposal writes exactly the posted (ticked)
  changes, with the posted (edited) values, through the normal save paths
  (tracking on the player / injury); answers ``saved`` (value + display per
  change), ``refresh`` (the read fragments) and ``saved_at``. Refused: a
  coach (403), a record of another player (403), a field outside the
  proposal allowlist (403), an invalid value (400 — and NOTHING is written,
  the apply is atomic).
* AC-6 Dismiss: the triggering save wrote only its own field; the proposal
  itself changes nothing until applied.
* AC-7 Create: a therapist creating an injury with a predicted resolution
  date (the full « new injury » page of the app) lands on a page that
  carries the proposal (``data-sc-proposal`` on the proposal sheet).
"""
import json

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.fragments_common_1611 import FragmentsCommon

D = fields.Date.to_date


class RetourPrevuFixtures:
    """Two extra injuries on ``player`` (PortalCovCommon's ``injury`` is active)."""

    @classmethod
    def _fixtures(cls):
        Injury = cls.env['sports.patient.injury']
        cls.injury.write({'predicted_resolution_date': '2030-03-01', 'diagnosis': 'Synthetic ankle'})
        cls.injury_b = Injury.create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic knee',
            'predicted_resolution_date': '2030-02-01'})
        cls.injury_b.with_context(mail_notrack=True).write({'stage': 'active'})
        # Ignored by every proposal: a resolved and an unverified injury.
        cls.old = Injury.create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic old',
            'predicted_resolution_date': '2031-01-01'})
        cls.old.with_context(mail_notrack=True).write({'stage': 'resolved', 'resolution_date': '2029-01-01'})
        cls.unverified = Injury.create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic unverified',
            'predicted_resolution_date': '2032-01-01'})
        cls.unverified.with_context(mail_notrack=True).write({'stage': 'unverified'})


@tagged('post_install', '-at_install')
class TestRetourPrevuBuilders1603(RetourPrevuFixtures, TransactionCase):
    """The proposal builders (model methods) on their own."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.player = cls.env['sports.patient'].create({'first_name': 'Rp', 'last_name': 'Synthetic'})
        cls.injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player.id, 'diagnosis': 'Synthetic ankle'})
        cls.injury.with_context(mail_notrack=True).write({'stage': 'active'})
        cls._fixtures()

    # -- AC-2 ------------------------------------------------------------
    def test_latest_active_date_ignores_resolved_and_unverified(self):
        self.assertEqual(self.player._sc_latest_active_predicted(), D('2030-03-01'))

    def test_injury_change_proposes_latest_active_date(self):
        proposal = self.player._retour_prevu_after_injury_change(self.injury_b)
        self.assertEqual(proposal['kind'], 'retour_prevu')
        self.assertEqual(proposal['patient_id'], self.player.id)
        [item] = proposal['items']
        self.assertEqual((item['model'], item['id'], item['field']),
                         ('sports.patient', self.player.id, 'predicted_return_date'))
        self.assertEqual(item['proposed'], '2030-03-01')
        self.assertEqual(item['current'], '')
        self.assertTrue(item['editable'])
        self.assertFalse(item['tickable'])
        self.assertTrue(item['checked'])
        self.assertTrue(proposal['title'] and proposal['message'])

    def test_injury_change_equal_date_proposes_nothing(self):
        self.player.predicted_return_date = '2030-03-01'
        self.assertIsNone(self.player._retour_prevu_after_injury_change(self.injury))

    def test_injury_change_of_inactive_injury_proposes_nothing(self):
        self.assertIsNone(self.player._retour_prevu_after_injury_change(self.old))
        self.assertIsNone(self.player._retour_prevu_after_injury_change(self.unverified))

    def test_injury_change_without_any_active_date_proposes_nothing(self):
        (self.injury | self.injury_b).write({'predicted_resolution_date': False})
        self.assertIsNone(self.player._retour_prevu_after_injury_change(self.injury))

    # -- AC-3 ------------------------------------------------------------
    def test_alignment_lists_each_differing_active_injury(self):
        for new in ('2030-04-15', '2030-01-10'):  # later, then earlier
            proposal = self.player._injuries_alignment_for(D(new))
            self.assertEqual(proposal['kind'], 'align_injuries')
            items = {item['id']: item for item in proposal['items']}
            self.assertEqual(set(items), {self.injury.id, self.injury_b.id})
            for item in items.values():
                self.assertEqual(item['model'], 'sports.patient.injury')
                self.assertEqual(item['field'], 'predicted_resolution_date')
                self.assertEqual(item['proposed'], new)
                self.assertTrue(item['tickable'] and item['checked'])
                self.assertFalse(item['editable'])
            self.assertIn('Synthetic knee', items[self.injury_b.id]['label'])

    def test_alignment_skips_injuries_already_on_the_date(self):
        proposal = self.player._injuries_alignment_for(D('2030-02-01'))
        # 2030-02-01 differs from the latest (03-01): only « ankle » differs.
        self.assertEqual([item['id'] for item in proposal['items']], [self.injury.id])

    def test_alignment_equal_to_latest_proposes_nothing(self):
        self.assertIsNone(self.player._injuries_alignment_for(D('2030-03-01')))

    def test_alignment_cleared_or_no_active_injury_proposes_nothing(self):
        self.assertIsNone(self.player._injuries_alignment_for(False))
        (self.injury | self.injury_b).with_context(mail_notrack=True).write({'stage': 'resolved'})
        self.assertIsNone(self.player._injuries_alignment_for(D('2030-05-01')))

    # -- AC-4 ------------------------------------------------------------
    def test_last_active_resolved_proposes_clear_and_actual_return(self):
        self.player.write({'predicted_return_date': '2030-03-01'})
        self.injury_b.with_context(mail_notrack=True).write({'stage': 'resolved', 'resolution_date': '2030-01-20'})
        self.assertIsNone(self.player._after_last_active_resolved(self.injury_b))
        self.injury.with_context(mail_notrack=True).write({'stage': 'resolved', 'resolution_date': '2030-02-20'})
        proposal = self.player._after_last_active_resolved(self.injury)
        self.assertEqual(proposal['kind'], 'last_resolved')
        items = {item['field']: item for item in proposal['items']}
        self.assertEqual(set(items), {'predicted_return_date', 'return_date'})
        self.assertEqual(items['predicted_return_date']['proposed'], '')
        self.assertEqual(items['predicted_return_date']['current'], '2030-03-01')
        self.assertFalse(items['predicted_return_date']['editable'])
        self.assertEqual(items['return_date']['proposed'], '2030-02-20')
        self.assertTrue(items['return_date']['editable'])
        for item in items.values():
            self.assertTrue(item['tickable'] and item['checked'])

    def test_last_active_resolved_with_nothing_to_change(self):
        self.player.write({'return_date': '2030-02-20'})
        (self.injury | self.injury_b).with_context(mail_notrack=True).write(
            {'stage': 'resolved', 'resolution_date': '2030-02-20'})
        self.assertIsNone(self.player._after_last_active_resolved(self.injury))


@tagged('post_install', '-at_install')
class TestRetourPrevuApp1603(RetourPrevuFixtures, FragmentsCommon):
    """The save route's ``propose``, the header field and the apply route."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._fixtures()
        cls.other_injury = cls.env['sports.patient.injury'].create({
            'patient_id': cls.player_b.id, 'diagnosis': 'Synthetic other'})

    def _url(self, tab='injuries'):
        return '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)

    def _apply(self, changes, patient=None):
        return self.url_open('/my/app/apply-proposal', data={
            'patient_id': (patient or self.player).id,
            'changes': json.dumps(changes),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    # -- AC-1 ------------------------------------------------------------
    def test_therapist_edits_retour_prevu_in_the_header(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        # Review fixes 2026-10-18: in the header's edit view (its pencil).
        section = tree.xpath('//*[@data-sc-section="player.hero"]/*[@data-sc-edit-view="edit"]'
                             '/*[@data-sc-section="player.predicted_return"]')
        self.assertEqual(len(section), 1)
        props = [json.loads(node.get('props')) for node in section[0].xpath('.//owl-component')]
        self.assertEqual([(p['field'], p['inputType']) for p in props], [('predicted_return_date', 'date')])
        self.assertTrue(props[0].get('clearable'))
        payload = self._saved(self.player, 'predicted_return_date', '2030-03-01')
        self.assertEqual(payload['value'], '2030-03-01')
        self.assertTrue(payload['display'])
        self.player.invalidate_recordset()
        self.assertEqual(self.player.predicted_return_date, D('2030-03-01'))
        self._saved(self.player, 'predicted_return_date', '')
        self.player.invalidate_recordset()
        self.assertFalse(self.player.predicted_return_date)

    @mute_logger('odoo.http')
    def test_invalid_date_refused(self):
        self._login_tp()
        self.assertEqual(self._save(self.player, 'predicted_return_date', 'nope').status_code, 400)

    @mute_logger('odoo.http')
    def test_coach_reads_and_cannot_save(self):
        # Review fixes 2026-10-18: the header's read view shows « Retour
        # prévu » while the player is not Play OK (the coach has no edit view).
        self.player.write({'predicted_return_date': '2030-03-01', 'match_status': 'no', 'practice_status': 'no'})
        self._login_coach()
        _text, tree = self._get(self._url())
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.predicted_return"]'))
        section = tree.xpath('//*[@data-sc-section="player.return"]')[0]
        self.assertFalse(section.xpath('.//owl-component'))
        self.assertEqual(section.get('data-sc-return-kind'), 'predicted')
        read = self._node(tree, 'sports.patient:%s:predicted-return' % self.player.id)
        self.assertIsNotNone(read)
        self.assertIn('2030', self._text(read))
        self.assertEqual(self._save(self.player, 'predicted_return_date', '2030-04-01').status_code, 403)

    # -- AC-2 / AC-6 -----------------------------------------------------
    def test_injury_date_save_proposes_player_date(self):
        self._login_tp()
        payload = self._saved(self.injury_b, 'predicted_resolution_date', '2030-05-01')
        proposal = payload['propose']
        self.assertEqual(proposal['kind'], 'retour_prevu')
        self.assertEqual(proposal['items'][0]['proposed'], '2030-05-01')
        # AC-6: the save wrote its own field only.
        self.player.invalidate_recordset()
        self.assertFalse(self.player.predicted_return_date)

    def test_injury_date_save_equal_proposes_nothing(self):
        self.player.write({'predicted_return_date': '2030-03-01'})
        self._login_tp()
        payload = self._saved(self.injury_b, 'predicted_resolution_date', '2030-02-15')
        self.assertNotIn('propose', payload)

    # -- AC-3 ------------------------------------------------------------
    def test_player_date_save_proposes_alignment(self):
        self._login_tp()
        payload = self._saved(self.player, 'predicted_return_date', '2030-06-01')
        proposal = payload['propose']
        self.assertEqual(proposal['kind'], 'align_injuries')
        self.assertEqual({item['id'] for item in proposal['items']}, {self.injury.id, self.injury_b.id})
        self.injury.invalidate_recordset()
        self.assertEqual(self.injury.predicted_resolution_date, D('2030-03-01'))

    # -- AC-4 ------------------------------------------------------------
    def test_resolving_last_active_injury_proposes_return(self):
        self.player.write({'predicted_return_date': '2030-03-01'})
        self._login_tp()
        self.assertNotIn('propose', self._saved(self.injury_b, 'stage', 'resolved'))
        payload = self._saved(self.injury, 'stage', 'resolved')
        proposal = payload['propose']
        self.assertEqual(proposal['kind'], 'last_resolved')
        today = fields.Date.to_string(fields.Date.context_today(self.injury))
        items = {item['field']: item for item in proposal['items']}
        self.assertEqual(items['return_date']['proposed'], today)
        self.assertEqual(items['predicted_return_date']['proposed'], '')

    # -- AC-5 ------------------------------------------------------------
    def test_apply_writes_only_the_posted_changes(self):
        self._login_tp()
        answer = self._apply([
            {'model': 'sports.patient', 'id': self.player.id, 'field': 'predicted_return_date',
             'value': '2030-07-04'},
            {'model': 'sports.patient.injury', 'id': self.injury_b.id,
             'field': 'predicted_resolution_date', 'value': '2030-07-04'},
        ])
        self.assertEqual(answer.status_code, 200, answer.text)
        payload = answer.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(len(payload['saved']), 2)
        saved = {(s['model'], s['id'], s['field']): s for s in payload['saved']}
        entry = saved[('sports.patient', self.player.id, 'predicted_return_date')]
        self.assertEqual(entry['value'], '2030-07-04')
        self.assertTrue(entry['display'] and entry['write_date'])
        self.assertTrue(payload['saved_at'])
        self.assertRefreshes(payload, 'sports.patient:%s:hero-chips' % self.player.id)
        self.assertRefreshes(payload, 'sports.patient.injury:%s:summary' % self.injury_b.id)
        self.player.invalidate_recordset()
        (self.injury | self.injury_b).invalidate_recordset()
        self.assertEqual(self.player.predicted_return_date, D('2030-07-04'))
        self.assertEqual(self.injury_b.predicted_resolution_date, D('2030-07-04'))
        self.assertEqual(self.injury.predicted_resolution_date, D('2030-03-01'))  # not ticked
        # Through the normal write path: tracked on the record.
        tracked = self.injury_b.sudo().message_ids.tracking_value_ids.filtered(
            lambda t: t.field_id.name == 'predicted_resolution_date')
        self.assertTrue(tracked)

    def test_apply_last_resolved_sets_actual_return_and_clears(self):
        self.player.write({'predicted_return_date': '2030-03-01'})
        self._login_tp()
        answer = self._apply([
            {'model': 'sports.patient', 'id': self.player.id, 'field': 'predicted_return_date', 'value': ''},
            {'model': 'sports.patient', 'id': self.player.id, 'field': 'return_date', 'value': '2030-02-27'},
        ])
        self.assertEqual(answer.status_code, 200, answer.text)
        self.player.invalidate_recordset()
        self.assertFalse(self.player.predicted_return_date)
        self.assertEqual(self.player.return_date, D('2030-02-27'))

    @mute_logger('odoo.http')
    def test_apply_refusals(self):
        change = {'model': 'sports.patient', 'id': self.player.id, 'field': 'predicted_return_date',
                  'value': '2030-07-04'}
        self._login_coach()
        self.assertEqual(self._apply([change]).status_code, 403)
        self._login_tp()
        # Another player's injury, under this player's proposal.
        foreign = {'model': 'sports.patient.injury', 'id': self.other_injury.id,
                   'field': 'predicted_resolution_date', 'value': '2030-07-04'}
        self.assertEqual(self._apply([foreign]).status_code, 403)
        # A field outside the proposal allowlist (even one the save route allows).
        self.assertEqual(self._apply([dict(change, field='allergies', value='x')]).status_code, 403)
        self.assertEqual(self._apply([dict(change, model='res.partner')]).status_code, 403)
        # Malformed.
        resp = self.url_open('/my/app/apply-proposal', data={
            'patient_id': self.player.id, 'changes': 'not json', 'csrf_token': self._csrf()})
        self.assertEqual(resp.status_code, 400)
        # Atomic: one invalid value -> nothing written.
        resp = self._apply([change, dict(change, field='return_date', value='nope')])
        self.assertEqual(resp.status_code, 400)
        self.player.invalidate_recordset()
        self.assertFalse(self.player.predicted_return_date)
        self.assertFalse(self.player.allergies)

    # -- AC-7 ------------------------------------------------------------
    def test_create_with_predicted_date_carries_the_proposal(self):
        self._login_tp()
        resp = self.url_open('/my/patient/injury/create', data={
            'csrf_token': self._csrf(), 'patient_id': self.player.id,
            'diagnosis': 'Synthetic new', 'injury_date': '2030-01-02',
            'predicted_resolution_date': '2030-09-09',
        }, allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        _text, tree = self._get(resp.headers['Location'])
        sheet = tree.xpath('//dialog[@id="sc_proposal_sheet"]')
        self.assertEqual(len(sheet), 1)
        proposal = json.loads(sheet[0].get('data-sc-proposal'))
        self.assertEqual(proposal['kind'], 'retour_prevu')
        self.assertEqual(proposal['items'][0]['proposed'], '2030-09-09')
        # Shown once: the next page does not carry it again.
        _text, tree = self._get(self._url())
        self.assertIsNone(tree.xpath('//dialog[@id="sc_proposal_sheet"]')[0].get('data-sc-proposal'))
