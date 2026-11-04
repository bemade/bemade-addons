"""Task 1670 — resolving a player's LAST active injury: the #1603
« last_resolved » proposal also offers Match / Practice back to « Yes ».
Synthetic fixtures only.

Acceptance criteria:

* AC-1 The proposal holds a ``match_status`` / ``practice_status`` row
  (``type: 'selection'``, proposed ``yes``, the field's own options,
  ticked, untickable) for each status that is not « Yes » — none when both
  are already « Yes », none at all for an injury that is not the last
  active one. The message mentions the statuses only when such rows exist.
* AC-2 Applying writes the pair in one go through the « sc_status » save
  (tracked like any status change); an unticked row leaves its status; a
  value changed in the sheet is applied; an invalid pair is refused (400)
  with the status pills' reason (« Requires Practice: Yes » / « Set Match
  to No first ») and nothing is written.
* AC-3 Coaches never apply a proposal (403, as before).
* AC-4 Browser (phone 390 px, tour ``sc_1670_last_statuses``): « Résoudre »
  on the last active injury → the sheet shows the status rows → Apply → the
  header pills read Match: Yes / Practice: Yes, no reload.
"""
import json

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_injury_quick_tours_1604 import QuickToursCommon


class Statuses1670Common(QuickToursCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The ankle (cls.injury) is the player's only ACTIVE injury (the
        # strain is unverified).
        cls.player.with_context(mail_notrack=True).write({'match_status': 'no', 'practice_status': 'no'})

    def _resolve(self, injury=None):
        injury = injury or self.injury
        injury.with_context(mail_notrack=True).write({'stage': 'resolved', 'resolution_date': '2025-01-15'})
        return self.player._after_last_active_resolved(injury)

    def _apply(self, changes):
        return self.url_open('/my/app/apply-proposal', data={
            'patient_id': self.player.id, 'changes': json.dumps(changes), 'csrf_token': self._csrf(),
        }, allow_redirects=False)

    def _change(self, field, value):
        return {'model': 'sports.patient', 'id': self.player.id, 'field': field, 'value': value}


@tagged('post_install', '-at_install')
class TestLastInjuryStatuses1670(Statuses1670Common):

    # -- AC-1 --------------------------------------------------------------
    def test_proposal_offers_the_statuses(self):
        proposal = self._resolve()
        items = {item['field']: item for item in proposal['items']}
        for field, options in (('match_status', ['yes', 'no']),
                               ('practice_status', ['yes', 'no_contact', 'no'])):
            item = items[field]
            self.assertEqual(item['type'], 'selection')
            self.assertEqual((item['current'], item['proposed']), ('no', 'yes'))
            self.assertEqual([o['value'] for o in item['options']], options)
            self.assertTrue(item['editable'] and item['tickable'] and item['checked'])
        self.assertIn('statuses', proposal['message'])

    def test_no_status_rows_when_already_yes(self):
        self.player.with_context(mail_notrack=True).write({'match_status': 'yes', 'practice_status': 'yes'})
        self.player.write({'predicted_return_date': '2030-03-01'})
        proposal = self._resolve()
        self.assertEqual({item['field'] for item in proposal['items']}, {'predicted_return_date', 'return_date'})
        self.assertNotIn('statuses', proposal['message'])

    def test_only_the_differing_status(self):
        self.player.with_context(mail_notrack=True).write({'match_status': 'no', 'practice_status': 'yes'})
        proposal = self._resolve()
        fields_ = {item['field'] for item in proposal['items']}
        self.assertIn('match_status', fields_)
        self.assertNotIn('practice_status', fields_)

    def test_not_the_last_injury(self):
        other = self.env['sports.patient.injury'].create({
            'patient_id': self.player.id, 'diagnosis': 'Synthetic other 1670'})
        other.with_context(mail_notrack=True).write({'stage': 'active'})
        self.assertIsNone(self._resolve())

    # -- AC-2 --------------------------------------------------------------
    def test_apply_writes_both_and_tracks(self):
        self._login_tp()
        resp = self._apply([self._change('match_status', 'yes'), self._change('practice_status', 'yes')])
        self.assertEqual(resp.status_code, 200, resp.text)
        saved = {entry['field'] for entry in resp.json()['saved']}
        self.assertEqual(saved, {'match_status', 'practice_status'})
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('yes', 'yes'))
        tracked = self.env['mail.tracking.value'].sudo().search([
            ('mail_message_id.model', '=', 'sports.patient'), ('mail_message_id.res_id', '=', self.player.id),
            ('field_id.name', 'in', ('match_status', 'practice_status'))])
        self.assertEqual(set(tracked.mapped('field_id.name')), {'match_status', 'practice_status'})

    def test_untick_leaves_the_status(self):
        self._login_tp()
        resp = self._apply([self._change('practice_status', 'no_contact')])
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('no', 'no_contact'))

    @mute_logger('odoo.http')
    def test_invalid_pair_refused(self):
        self._login_tp()
        resp = self._apply([self._change('match_status', 'yes')])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], 'Requires Practice: Yes')
        self.player.with_context(mail_notrack=True).write({'match_status': 'yes', 'practice_status': 'yes'})
        resp = self._apply([self._change('practice_status', 'no')])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['message'], 'Set Match to No first')
        resp = self._apply([self._change('match_status', 'maybe')])
        self.assertEqual(resp.status_code, 400)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('yes', 'yes'))

    @mute_logger('odoo.http')
    def test_invalid_pair_writes_nothing_else(self):
        self._login_tp()
        resp = self._apply([self._change('return_date', '2025-01-15'), self._change('match_status', 'yes')])
        self.assertEqual(resp.status_code, 400)
        self.player.invalidate_recordset()
        self.assertFalse(self.player.return_date)

    # -- AC-3 --------------------------------------------------------------
    @mute_logger('odoo.http')
    def test_coach_refused(self):
        self._login_coach()
        resp = self._apply([self._change('match_status', 'yes'), self._change('practice_status', 'yes')])
        self.assertEqual(resp.status_code, 403)


@tagged('post_install', '-at_install')
class TestLastInjuryStatusesTour1670(Statuses1670Common):
    browser_size = '390x844'

    def test_resolve_last_then_apply_statuses(self):
        self.start_tour('/my/player?player_id=%s&tab=injuries' % self.player.id, 'sc_1670_last_statuses',
                        login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual((self.player.match_status, self.player.practice_status), ('yes', 'yes'))
